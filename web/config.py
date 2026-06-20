"""웹 서비스 설정 (.env 에서 로드)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# 세션 서명 키 (운영에선 반드시 무작위 값으로)
SECRET_KEY = os.getenv("WEB_SECRET_KEY", "dev-insecure-change-me")

# DB: 로컬은 SQLite, 클라우드는 DATABASE_URL(Postgres)로 덮어쓰기
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'web.sqlite'}")

# 서비스 기본 URL (OAuth 콜백/이메일 버튼 링크에 사용)
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# 구글 OAuth (운영 로그인). 없으면 구글 로그인 버튼 비활성.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# 로컬 테스트용 임시 로그인 허용 (운영에선 false)
ALLOW_DEV_LOGIN = os.getenv("ALLOW_DEV_LOGIN", "true").lower() == "true"


def has_google_oauth() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
