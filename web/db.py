"""DB 모델 및 세션 (SQLAlchemy 2.0)."""
import datetime as dt
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, func,
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker,
)

from . import config as webcfg


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    google_sub: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    keywords_text: Mapped[str] = mapped_column(Text, default="")   # 줄바꿈 구분
    digest_email: Mapped[str] = mapped_column(String(320), default="")
    max_papers: Mapped[int] = mapped_column(Integer, default=5)
    days_back: Mapped[int] = mapped_column(Integer, default=90)
    send_hour: Mapped[int] = mapped_column(Integer, default=8)     # 0~23 (현지시각)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="subscription")

    @property
    def keywords(self) -> List[str]:
        return [k.strip() for k in self.keywords_text.replace(",", "\n").splitlines() if k.strip()]


class SentLog(Base):
    __tablename__ = "sent_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    paper_key: Mapped[str] = mapped_column(String(400), index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    journal: Mapped[str] = mapped_column(String(400), default="")
    impact_factor: Mapped[Optional[float]] = mapped_column(default=None)
    doi: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    saved: Mapped[bool] = mapped_column(Boolean, default=False)   # 이메일 버튼으로 저장됨
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


_db_url = webcfg.DATABASE_URL
# 일부 호스트/Supabase가 주는 옛 스킴 정규화
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}
_engine_kwargs = {"connect_args": _connect_args, "future": True}
if not _db_url.startswith("sqlite"):
    # 클라우드 DB 연결 끊김 대비
    _engine_kwargs["pool_pre_ping"] = True

engine = create_engine(_db_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db():
    # SQLite(로컬)일 때만 data 디렉터리 필요. Postgres(배포)면 생략.
    if _db_url.startswith("sqlite"):
        from pathlib import Path
        try:
            Path(webcfg.ROOT / "data").mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    Base.metadata.create_all(engine)
