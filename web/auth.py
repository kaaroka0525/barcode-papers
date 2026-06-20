"""인증: 구글 OAuth(운영) + 임시 로그인(로컬 테스트)."""
import logging

from authlib.integrations.starlette_client import OAuth

from . import config as webcfg
from .db import Subscription, User

log = logging.getLogger("web.auth")

oauth = OAuth()
if webcfg.has_google_oauth():
    oauth.register(
        name="google",
        client_id=webcfg.GOOGLE_CLIENT_ID,
        client_secret=webcfg.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def get_or_create_user(db, email: str, name: str = "", google_sub: str = None) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, name=name or email.split("@")[0], google_sub=google_sub)
        db.add(user)
        db.flush()
        # 기본 구독 생성: 수신 이메일을 로그인 이메일로 미리 채움
        db.add(Subscription(user_id=user.id, digest_email=email))
        db.commit()
        db.refresh(user)
    else:
        if google_sub and not user.google_sub:
            user.google_sub = google_sub
            db.commit()
    return user


def current_user(request, db):
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()
