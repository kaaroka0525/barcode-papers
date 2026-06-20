"""사용자별 다이제스트 실행 — 기존 barcode_papers 파이프라인 재사용."""
import dataclasses
import logging

from barcode_papers import email_send, impact, pdfs, search, summarize
from barcode_papers.config import load_config
from barcode_papers.run import order_by_if, select_by_relevance

from .db import SentLog

log = logging.getLogger("web.service")


def _user_config(sub):
    base = load_config()
    return dataclasses.replace(
        base,
        keywords=sub.keywords,
        recipients=[sub.digest_email],
        max_papers=sub.max_papers,
        days_back=sub.days_back,
    )


def run_for_user(db, user, *, ignore_sent: bool = False) -> dict:
    sub = user.subscription
    if not sub or not sub.active:
        return {"status": "skip", "reason": "비활성 또는 구독 없음"}
    if not sub.keywords:
        return {"status": "skip", "reason": "키워드 없음"}
    if not sub.digest_email:
        return {"status": "skip", "reason": "수신 이메일 없음"}

    cfg = _user_config(sub)
    if not cfg.gmail_app_password:
        return {"status": "error", "reason": "GMAIL_APP_PASSWORD 미설정(.env)"}

    candidates = search.search_all(cfg)
    if not ignore_sent:
        sent_keys = {
            row[0] for row in db.query(SentLog.paper_key).filter(SentLog.user_id == user.id)
        }
        candidates = [p for p in candidates if p.key not in sent_keys]

    if not candidates:
        return {"status": "empty", "reason": "보낼 새 논문 없음"}

    top = select_by_relevance(candidates, cfg.max_papers)
    impact.annotate(top, cfg)
    top = order_by_if(top)
    summarize.summarize_all(top, cfg)
    for p in top:
        path = pdfs.download_pdf(p)
        if path:
            p.figures = pdfs.extract_figures(path)

    message = email_send.build_email(top, cfg)
    email_send.send_email(message, cfg)

    for p in top:
        db.add(SentLog(
            user_id=user.id, paper_key=p.key, title=p.title,
            journal=p.journal, impact_factor=p.impact_factor, doi=p.doi,
        ))
    db.commit()

    return {"status": "sent", "count": len(top),
            "titles": [p.title for p in top]}
