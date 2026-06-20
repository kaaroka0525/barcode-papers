"""설정(config.yaml) + 비밀값(.env) 로딩."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# 서버리스(Vercel)는 프로젝트 경로가 읽기 전용 → 쓰기 가능한 /tmp 사용
if os.getenv("VERCEL"):
    DATA_DIR = Path("/tmp/barcode_data")
else:
    DATA_DIR = ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
DB_PATH = DATA_DIR / "state.sqlite"


def ensure_data_dirs():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PDF_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


@dataclass
class Config:
    keywords: List[str]
    recipients: List[str]
    sender: str
    max_papers: int = 5
    candidate_pool_per_keyword: int = 30
    days_back: int = 30
    summary_model: str = "claude-haiku-4-5-20251001"
    openalex_mailto: str = ""
    hanyang_proxy_template: str = "https://login.libproxy.hanyang.ac.kr/login?url={url}"
    gdrive_remote: str = "gdrive"
    gdrive_folder: str = "로봇디자인 논문 아카이브"
    # .env 에서 옴
    gmail_app_password: str = field(default="", repr=False)
    anthropic_api_key: str = field(default="", repr=False)
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key.strip())

    def proxy_link(self, url: str) -> str:
        if not url:
            return ""
        try:
            return self.hanyang_proxy_template.format(url=url)
        except Exception:
            return url


def load_config(config_path: Path = None) -> Config:
    config_path = config_path or (ROOT / "config.yaml")
    load_dotenv(ROOT / ".env")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    # 앱 비밀번호의 공백 제거 (Gmail은 공백 없이도 동작)
    app_pw = (os.getenv("GMAIL_APP_PASSWORD", "") or "").replace(" ", "")

    return Config(
        keywords=raw.get("keywords", []),
        recipients=raw.get("recipients", []),
        sender=raw.get("sender", ""),
        max_papers=int(raw.get("max_papers", 5)),
        candidate_pool_per_keyword=int(raw.get("candidate_pool_per_keyword", 30)),
        days_back=int(raw.get("days_back", 30)),
        summary_model=raw.get("summary_model", "claude-haiku-4-5-20251001"),
        openalex_mailto=raw.get("openalex_mailto", ""),
        hanyang_proxy_template=raw.get(
            "hanyang_proxy_template",
            "https://login.libproxy.hanyang.ac.kr/login?url={url}",
        ),
        gdrive_remote=raw.get("gdrive_remote", "gdrive"),
        gdrive_folder=raw.get("gdrive_folder", "로봇디자인 논문 아카이브"),
        gmail_app_password=app_pw,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "") or "",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "") or "",
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )
