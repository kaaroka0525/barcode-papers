"""엔트리포인트: 검색 → 중복제거 → IF 정렬 → 요약/PDF → 이메일 발송.

사용 예:
    python -m barcode_papers.run --dry-run     # 발송 없이 콘솔 출력
    python -m barcode_papers.run --test-email  # 중복 무시하고 1회 실제 발송
    python -m barcode_papers.run               # 정규 일일 실행
"""
import argparse
import json
import logging
import sys

from . import email_send, impact, pdfs, search, state, summarize
from .config import DATA_DIR, load_config

LAST_DIGEST_PATH = DATA_DIR / "last_digest.json"

log = logging.getLogger("barcode_papers")


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # impact_factor 패키지의 SQLAlchemy 쿼리 로그 소음 제거
    for name in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.engine.Engine"):
        logging.getLogger(name).setLevel(logging.WARNING)


def select_by_relevance(papers, max_papers):
    """주제 적합도(relevance) 높은 순으로 상위 N편을 '선별'."""
    return sorted(
        papers, key=lambda p: (p.relevance_score or 0.0), reverse=True
    )[:max_papers]


def order_by_if(papers):
    """선별된 논문을 이메일 표시용으로 IF 내림차순 '정렬'. IF 없는 논문은 뒤로."""
    return sorted(
        papers,
        key=lambda p: (p.impact_factor is not None, p.impact_factor or -1.0),
        reverse=True,
    )


def run(dry_run=False, test_email=False, days_back=None, max_papers=None):
    config = load_config()
    if days_back is not None:
        config.days_back = days_back
    if max_papers is not None:
        config.max_papers = max_papers

    log.info("키워드: %s", ", ".join(config.keywords))
    candidates = search.search_all(config)
    log.info("후보 논문 총 %d편", len(candidates))

    if not test_email:
        candidates = state.filter_unseen(candidates)
        log.info("신규(미발송) 논문 %d편", len(candidates))

    if not candidates:
        log.info("보낼 새 논문이 없습니다. 종료.")
        return

    # 1) 주제 적합도로 먼저 선별
    top = select_by_relevance(candidates, config.max_papers)
    log.info("적합도 상위 %d편 선별", len(top))
    # 2) 선별된 논문만 IF 조회 후 IF 순으로 정렬
    impact.annotate(top, config)
    top = order_by_if(top)

    # 요약 + PDF + figure
    summarize.summarize_all(top, config)
    for p in top:
        path = pdfs.download_pdf(p)
        if path:
            p.figures = pdfs.extract_figures(path)

    # 나중에 번호로 아카이브할 수 있도록 이번 다이제스트를 저장
    try:
        with open(LAST_DIGEST_PATH, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in top], f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("last_digest 저장 실패: %s", e)

    # 콘솔 미리보기
    print("\n" + "=" * 70)
    for i, p in enumerate(top, 1):
        print(f"[{i}] {p.title}")
        print(f"    저널: {p.journal} | {p.if_display}")
        print(f"    PDF: {'첨부' if p.pdf_path else '없음(유료/비공개)'} | figure {len(p.figures)}개")
        print(f"    {p.summary.splitlines()[0] if p.summary else ''}")
    print("=" * 70 + "\n")

    if dry_run:
        log.info("[dry-run] 메일을 보내지 않고 종료합니다.")
        return

    email_send.deliver(top, config)

    if not test_email:
        state.mark_sent(top)
        log.info("발송 이력 기록 완료.")
    else:
        log.info("[test-email] 발송 이력은 기록하지 않습니다.")


def main():
    _setup_logging()
    parser = argparse.ArgumentParser(description="매일 논문 다이제스트 발송")
    parser.add_argument("--dry-run", action="store_true", help="발송 없이 콘솔 출력만")
    parser.add_argument("--test-email", action="store_true", help="중복 무시하고 1회 실제 발송(이력 미기록)")
    parser.add_argument("--days-back", type=int, default=None, help="최근성 창(일) 덮어쓰기")
    parser.add_argument("--max", type=int, default=None, dest="max_papers", help="최대 편수 덮어쓰기")
    args = parser.parse_args()

    try:
        run(
            dry_run=args.dry_run,
            test_email=args.test_email,
            days_back=args.days_back,
            max_papers=args.max_papers,
        )
    except Exception as e:
        log.exception("실행 실패: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
