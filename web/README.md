# 웹 서비스 (다중 사용자 논문 다이제스트)

기존 `barcode_papers` 파이프라인을 재사용한 FastAPI 웹앱입니다.
사용자가 로그인 → 키워드/이메일 등록 → 매일 정해진 시각 자동 발송.

## 로컬 실행
```bash
cd ~/AI_Projects_2026/barcode
python3 -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
# 브라우저: http://127.0.0.1:8000
```
- 로컬 테스트는 랜딩의 **테스트 로그인**(이메일 입력)으로 바로 가능
- 요약은 로컬 `claude` CLI 사용, 메일은 기존 Gmail SMTP(.env의 GMAIL_APP_PASSWORD) 사용

## 구조
```
web/
  app.py        FastAPI 라우트(랜딩/대시보드/로그인/지금보내기)
  db.py         User / Subscription / SentLog (SQLAlchemy)
  auth.py       구글 OAuth + 임시 로그인
  service.py    사용자별 파이프라인 실행(검색→IF→요약→발송, per-user 중복제거)
  scheduler.py  APScheduler 매시 정각 → send_hour 매칭 사용자 발송
  templates/    landing.html, dashboard.html, base.html
  static/       style.css
```

## 환경변수 (.env)
| 키 | 용도 |
|---|---|
| `GMAIL_APP_PASSWORD` | 메일 발송(로컬/임시). 배포 시 Resend로 교체 권장 |
| `WEB_SECRET_KEY` | 세션 서명 키 (운영 필수: 무작위 값) |
| `DATABASE_URL` | 미설정 시 SQLite. 클라우드는 Postgres URL |
| `BASE_URL` | OAuth 콜백/링크 기준 URL |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | 구글 로그인(운영) |
| `ALLOW_DEV_LOGIN` | 로컬 임시 로그인 허용(운영 false) |

## 남은 단계 (배포 전)
1. **구글 OAuth 클라이언트** 생성 → CLIENT_ID/SECRET 발급, 콜백 `BASE_URL/auth/google/callback` 등록
2. **이메일 전송 서비스(Resend 등)** 연결 — 개인 Gmail은 대량 발송 부적합
3. **요약용 Anthropic API 키** — 서버에선 claude CLI 대신 API 사용
4. **클라우드 배포**(Railway/Render/Fly.io) + Postgres + 항상-켜짐(스케줄러용)
5. (확장) 이메일 내 "드라이브 저장" 버튼 + 내 라이브러리 페이지
