"""FastAPI 앱 — 로그인, 키워드/이메일 등록, 일일 자동 발송."""
import datetime as dt
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth
from . import config as webcfg
from .db import SentLog, Subscription, User, SessionLocal, init_db
from .service import run_for_user

# Vercel(서버리스)에서는 항상-켜진 스케줄러 대신 Vercel Cron을 사용
ON_VERCEL = bool(os.getenv("VERCEL"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _n in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.engine.Engine"):
    logging.getLogger(_n).setLevel(logging.WARNING)

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))

app = FastAPI(title="논문 다이제스트")
app.add_middleware(SessionMiddleware, secret_key=webcfg.SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_flash(request: Request, msg: str, level: str = "success"):
    request.session["flash"] = {"msg": msg, "level": level}


@app.on_event("startup")
def _startup():
    init_db()
    if not ON_VERCEL:
        # 로컬/항상-켜진 호스트에서만 내장 스케줄러 사용
        from .scheduler import start_scheduler
        start_scheduler()


# ---------- 페이지 ----------
@app.get("/", response_class=HTMLResponse)
def landing(request: Request, db=Depends(get_db)):
    user = auth.current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {
        "has_google": webcfg.has_google_oauth(),
        "allow_dev": webcfg.ALLOW_DEV_LOGIN,
    })


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db=Depends(get_db)):
    user = auth.current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=302)
    sub = user.subscription
    recent = (
        db.query(SentLog).filter(SentLog.user_id == user.id)
        .order_by(SentLog.sent_at.desc()).limit(10).all()
    )
    flash = request.session.pop("flash", None)
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "sub": sub,
        "recent": recent, "flash": flash,
    })


@app.post("/dashboard")
def save_dashboard(
    request: Request,
    keywords_text: str = Form(""),
    digest_email: str = Form(""),
    max_papers: int = Form(5),
    days_back: int = Form(90),
    send_hour: int = Form(8),
    active: str = Form(None),
    db=Depends(get_db),
):
    user = auth.current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=302)
    sub = user.subscription
    if sub is None:
        sub = Subscription(user_id=user.id)
        db.add(sub)
    sub.keywords_text = keywords_text.strip()
    sub.digest_email = digest_email.strip() or user.email
    sub.max_papers = max(1, min(int(max_papers), 20))
    sub.days_back = max(1, min(int(days_back), 365))
    sub.send_hour = max(0, min(int(send_hour), 23))
    sub.active = active is not None
    db.commit()
    if not sub.keywords:
        set_flash(request, "저장했지만 선택된 키워드가 없습니다. 키워드를 추가하고 체크해 주세요.", "warning")
    else:
        set_flash(request, f"설정을 저장했습니다. (키워드 {len(sub.keywords)}개)")
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/send-now")
def send_now(request: Request, db=Depends(get_db)):
    user = auth.current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=302)
    try:
        result = run_for_user(db, user, ignore_sent=True)
    except Exception as e:
        logging.exception("send-now 실패")
        result = {"status": "error", "reason": str(e)}
    status = result["status"]
    msg, level = {
        "sent": (f"메일을 발송했습니다 ({result.get('count', 0)}편). 받은편지함을 확인하세요.", "success"),
        "empty": ("⚠️ 검색 결과 0건 — 메일을 보내지 않았습니다. 키워드를 더 넓게 쓰거나 '최근성(일)'을 늘려보세요.", "warning"),
        "skip": (f"⚠️ 건너뜀: {result.get('reason', '')}", "warning"),
        "error": (f"❌ 오류: {result.get('reason', '')}", "error"),
    }.get(status, (str(result), "warning"))
    set_flash(request, msg, level)
    return RedirectResponse("/dashboard", status_code=302)


# ---------- 인증 ----------
@app.get("/login/google")
async def login_google(request: Request):
    if not webcfg.has_google_oauth():
        return RedirectResponse("/", status_code=302)
    redirect_uri = webcfg.BASE_URL.rstrip("/") + "/auth/google/callback"
    return await auth.oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request, db=Depends(get_db)):
    token = await auth.oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or {}
    email = info.get("email")
    if not email:
        return RedirectResponse("/", status_code=302)
    user = auth.get_or_create_user(db, email, info.get("name", ""), info.get("sub"))
    request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/login/dev")
def login_dev(request: Request, email: str = Form(...), db=Depends(get_db)):
    if not webcfg.ALLOW_DEV_LOGIN:
        return RedirectResponse("/", status_code=302)
    user = auth.get_or_create_user(db, email.strip().lower())
    request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# ---------- Cron (Vercel Cron이 매일 호출) ----------
@app.get("/cron/run")
def cron_run(request: Request, db=Depends(get_db)):
    secret = os.getenv("CRON_SECRET")
    if secret:
        if request.headers.get("authorization", "") != f"Bearer {secret}":
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    subs = db.query(Subscription).filter(Subscription.active.is_(True)).all()
    results = []
    for sub in subs:
        user = db.query(User).filter(User.id == sub.user_id).first()
        if not user:
            continue
        try:
            r = run_for_user(db, user)  # 중복 제외 ON
        except Exception as e:
            logging.exception("cron 발송 실패: %s", user.email)
            r = {"status": "error", "reason": str(e)}
        results.append({"email": user.email, **r})
    return JSONResponse({"processed": len(results), "results": results})
