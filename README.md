# 매일 논문 다이제스트 (barcode_papers)

키워드를 등록해두면 **매일 아침 8시**에 새 논문을 자동으로 찾아 요약·PDF와 함께
이메일(`kaaroka@gmail.com`)로 보내주는 파이프라인입니다.

## 동작 흐름
1. `config.yaml`의 키워드로 OpenAlex에서 최근 논문 검색
2. 이미 보낸 논문(DOI 기준)은 제외 (`data/state.sqlite`)
3. 저널 **Impact Factor 기준 상위 5편** 선정 (논문마다 저널명 + IF 표기)
4. Claude로 한국어 요약 + 무료 PDF(OA)에서 핵심 figure 추출
5. HTML 이메일로 발송 (무료 PDF 첨부 / 유료는 한양대 프록시 링크)

## 설정 바꾸기
`config.yaml` 한 파일만 수정하면 됩니다.
- `keywords`: 검색 키워드 (추가/삭제 자유)
- `max_papers`: 하루 발송 편수 (기본 5)
- `days_back`: 최근 며칠 이내 논문 (기본 30)
- `summary_model`: 요약 모델
- `hanyang_proxy_template`: 한양대 도서관 프록시 링크 형식 (정확한 형식으로 교체 권장)

## 비밀값 (`.env`)
- `GMAIL_APP_PASSWORD`: Gmail 앱 비밀번호 (발급 완료)
- `ANTHROPIC_API_KEY`: **비워둬도 됩니다.** 비어 있으면 설치된 `claude` CLI(Claude Code)로
  요약합니다(별도 키·비용 불필요). 키를 넣으면 Anthropic SDK를 우선 사용합니다.

### 요약 백엔드 우선순위
1. `ANTHROPIC_API_KEY` 있으면 → Anthropic SDK
2. 없으면 → 로컬 `claude` CLI (현재 이 방식 사용 중)
3. 둘 다 불가 → 초록 원문 그대로

## 수동 실행
```bash
cd ~/AI_Projects_2026/barcode
python3 -m barcode_papers.run --dry-run     # 발송 없이 콘솔 미리보기
python3 -m barcode_papers.run --test-email  # 중복 무시하고 1회 실제 발송(이력 미기록)
python3 -m barcode_papers.run               # 정규 실행 (발송 + 이력 기록)
# 옵션: --days-back 60 (최근성 창), --max 10 (편수)
```

## 자동 실행 (매일 08:00, macOS launchd)
설치됨: `~/Library/LaunchAgents/com.barcode.papers.daily.plist`
```bash
launchctl list | grep barcode          # 등록 확인
launchctl start com.barcode.papers.daily   # 지금 즉시 1회 실행
launchctl unload ~/Library/LaunchAgents/com.barcode.papers.daily.plist   # 중지
launchctl load   ~/Library/LaunchAgents/com.barcode.papers.daily.plist   # 재시작
```
- 로그: `data/daily.log`, `data/daily.err.log`
- ⚠️ 맥이 켜져 있어야 실행됩니다. 8시에 슬립 상태면 깨우도록 설정하려면:
  `sudo pmset repeat wakeorpoweron MTWRFSU 07:58:00`
- `config.yaml`을 바꾸면 자동으로 반영됩니다(재로드 불필요). 단 python 경로·스케줄 시간을
  바꾸려면 plist 수정 후 unload/load 하세요.

## 알려진 한계
- 유료 논문 PDF는 자동 첨부 불가(기관 SSO 자동화 불가) → 링크/프록시 링크로 제공
- IF는 JCR(impact_factor 패키지) 우선, 미매칭 시 OpenAlex 2년 평균 피인용수(추정)
- figure 추출은 OA PDF에 한해 휴리스틱으로 동작(논문에 따라 0개일 수 있음)

## 마음에 든 논문 아카이브 (Google Drive)
이메일을 보고 마음에 든 논문을 골라 드라이브에 정리합니다.
```bash
python3 -m barcode_papers.archive 1 3   # 직전 메일의 1, 3번 논문
python3 -m barcode_papers.archive all   # 직전 메일 전부
python3 -m barcode_papers.archive 10.1016/...   # DOI 직접 지정
python3 -m barcode_papers.archive 1 --no-upload # 드라이브 업로드 없이 로컬만
```
동작:
- `data/archive.xlsx` 에 누적(추가날짜·제목·저자·저널·IF·DOI·링크·프록시·요약 등, DOI 중복 제거)
- 무료(OA) PDF는 `data/archive/` 에 저장
- **rclone로 드라이브 `로봇디자인 논문 아카이브` 폴더에 자동 업로드**
  (엑셀은 덮어쓰기 갱신 → 한 파일에 계속 누적, PDF는 `pdf/` 하위로)

### rclone(드라이브 연동) 재설정이 필요할 때
```bash
rclone config            # 대화형: 새 remote 'gdrive', storage 'drive', scope 1(full)
rclone listremotes       # gdrive: 가 보이면 정상
```
드라이브 폴더명/원격명은 `config.yaml` 의 `gdrive_folder`, `gdrive_remote` 에서 변경.
