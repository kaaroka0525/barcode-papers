"""APScheduler — 매시 정각에 해당 시각으로 설정된 사용자들에게 다이제스트 발송."""
import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .db import SessionLocal, Subscription, User
from .service import run_for_user

log = logging.getLogger("web.scheduler")
_scheduler = None


def _hourly_job():
    hour = dt.datetime.now().hour
    db = SessionLocal()
    try:
        subs = (
            db.query(Subscription)
            .filter(Subscription.active.is_(True), Subscription.send_hour == hour)
            .all()
        )
        log.info("스케줄 작업: %d시, 대상 구독 %d건", hour, len(subs))
        for sub in subs:
            user = db.query(User).filter(User.id == sub.user_id).first()
            if not user:
                continue
            try:
                result = run_for_user(db, user)
                log.info("[%s] %s", user.email, result)
            except Exception as e:
                log.exception("사용자 %s 발송 실패: %s", user.email, e)
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    # 매시 정각 실행 → 사용자별 send_hour 와 매칭
    _scheduler.add_job(_hourly_job, "cron", minute=0, id="daily_digest")
    _scheduler.start()
    log.info("스케줄러 시작(매시 정각).")
