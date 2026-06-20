# 배포 가이드 (Supabase + Railway)

이 앱은 항상 켜진 백엔드(매일 스케줄러)가 필요해서 **Railway**에 올리고,
DB는 **Supabase(Postgres)**를 씁니다. (Vercel은 스케줄러를 못 돌려 백엔드용으로 부적합)

배포 순서대로 진행하세요. 각 단계에서 받은 값은 마지막 Railway 환경변수에 넣습니다.

---

## 1) Supabase — 데이터베이스
1. https://supabase.com → 로그인 → **New project**
2. 프로젝트 이름/DB 비밀번호 설정 → 생성(1~2분)
3. 좌측 **Project Settings → Database → Connection string → URI** 복사
   - `postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres`
   - `[PASSWORD]`를 위에서 정한 비밀번호로 교체 → 이게 **DATABASE_URL**

## 2) Gemini — 무료 요약 키 (서버 요약용)
1. https://aistudio.google.com/apikey → **Create API key** → 복사 = **GEMINI_API_KEY**
2. 무료 티어로 충분(Gemini Flash: 분당 15회·일 1500회 수준). 과금 설정 불필요.
   - 키워드 한글→영어 번역은 무료 라이브러리(deep-translator)로 자동 처리(키 불필요).
   - (선택) 더 높은 품질을 원하면 나중에 유료 `ANTHROPIC_API_KEY` 추가 가능(있으면 우선 사용).

## 3) 코드 업로드 (GitHub 또는 Railway CLI)
- **방법 A: GitHub** (권장)
  1. github.com에서 새 private 저장소 생성
  2. 터미널에서:
     ```
     cd ~/AI_Projects_2026/barcode
     git remote add origin https://github.com/<아이디>/<레포>.git
     git branch -M main
     git push -u origin main
     ```
- **방법 B: Railway CLI** (GitHub 없이)
  ```
  npm i -g @railway/cli   # 또는: brew install railway
  railway login
  railway init
  railway up
  ```

## 4) Railway — 배포
1. https://railway.app → 로그인 → **New Project**
2. (방법 A) **Deploy from GitHub repo** → 위 저장소 선택
3. 빌드/시작은 자동(`Procfile` 인식: `uvicorn web.app:app`)
4. **Variables(환경변수)** 에 아래 추가:
   | 키 | 값 |
   |---|---|
   | `DATABASE_URL` | (1단계 Supabase URI) |
   | `GEMINI_API_KEY` | (2단계 무료 키) |
   | `GMAIL_APP_PASSWORD` | 기존 Gmail 앱 비밀번호 |
   | `WEB_SECRET_KEY` | 길고 무작위한 문자열 |
   | `ALLOW_DEV_LOGIN` | `false` |
   | `BASE_URL` | (배포 후 받은 도메인, 5단계에서 갱신) |
   | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | (6단계에서) |
5. 배포되면 **Settings → Networking → Generate Domain** → `https://xxxx.up.railway.app`
   - 이 주소를 `BASE_URL` 에 넣고 재배포

## 5) Google 로그인 (OAuth)
1. https://console.cloud.google.com → 새 프로젝트
2. **APIs & Services → OAuth consent screen** → External → 앱 이름/이메일 입력
3. **Credentials → Create Credentials → OAuth client ID → Web application**
4. **Authorized redirect URIs** 에 추가:
   `https://xxxx.up.railway.app/auth/google/callback`
5. 생성된 **Client ID / Secret** → Railway 환경변수 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 에 입력 → 재배포

## 6) 확인
- `https://xxxx.up.railway.app` 접속 → **Google 계정으로 시작하기** 보임
- 로그인 → 키워드 등록 → "지금 한 번 보내보기" → 메일 수신 확인

---

## 나중에 개선
- **이메일**: 사용자가 늘면 Gmail SMTP → **Resend**(무료 3천통/월)로 교체
- **이메일 내 '드라이브 저장' 버튼** + 내 라이브러리 페이지
- 스케줄러 다중 인스턴스 시 중복 방지(현재 단일 인스턴스 가정)
