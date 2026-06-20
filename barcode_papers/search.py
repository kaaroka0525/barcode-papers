"""OpenAlex로 키워드별 최근 논문을 검색해 Paper 목록으로 정규화."""
import datetime as dt
import logging
from typing import Dict, List

import requests

from . import summarize
from .models import Paper

log = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"


def _reconstruct_abstract(inverted_index: dict) -> str:
    """OpenAlex의 abstract_inverted_index → 평문 초록 복원."""
    if not inverted_index:
        return ""
    positions: Dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions))


def _clean_doi(doi: str) -> str:
    if not doi:
        return ""
    return doi.replace("https://doi.org/", "").strip()


def _parse_work(work: dict, keyword: str) -> Paper:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    best_oa = work.get("best_oa_location") or {}
    oa = work.get("open_access") or {}

    authors = [
        (a.get("author") or {}).get("display_name", "")
        for a in (work.get("authorships") or [])
    ]
    authors = [a for a in authors if a]

    pdf_url = best_oa.get("pdf_url") or primary.get("pdf_url") or ""
    landing = (
        best_oa.get("landing_page_url")
        or primary.get("landing_page_url")
        or work.get("doi")
        or ""
    )

    issn = None
    issn_l = source.get("issn_l")
    issns = source.get("issn") or []
    issn = issn_l or (issns[0] if issns else None)

    return Paper(
        title=work.get("title") or work.get("display_name") or "(제목 없음)",
        authors=authors,
        year=work.get("publication_year"),
        journal=source.get("display_name") or "(저널 미상)",
        issn=issn,
        doi=_clean_doi(work.get("doi") or ""),
        landing_url=landing,
        pdf_url=pdf_url or "",
        is_oa=bool(oa.get("is_oa")),
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        matched_keyword=keyword,
        relevance_score=work.get("relevance_score"),
        # source 객체에는 작업 응답에 통계가 없으므로 impact 단계에서 별도 조회
        openalex_2yr=None,
    )


def search_keyword(keyword: str, *, days_back: int, per_page: int, mailto: str,
                   display: str = None) -> List[Paper]:
    from_date = (dt.date.today() - dt.timedelta(days=days_back)).isoformat()
    # title_and_abstract.search 로 주제 정확도를 높이고, 적합도(relevance) 순으로 가져옴.
    params = {
        "filter": (
            f"title_and_abstract.search:{keyword},"
            f"from_publication_date:{from_date},type:article"
        ),
        "sort": "relevance_score:desc",
        "per_page": min(per_page, 50),
    }
    if mailto:
        params["mailto"] = mailto

    try:
        resp = requests.get(OPENALEX_WORKS, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("OpenAlex 검색 실패 [%s]: %s", keyword, e)
        return []

    results = resp.json().get("results", [])
    label = display or keyword
    papers = [_parse_work(w, label) for w in results]
    log.info("키워드 '%s': %d편 수집", label, len(papers))
    return papers


def search_all(config) -> List[Paper]:
    """모든 키워드 검색 후 key 기준 중복 제거."""
    seen = {}
    for kw in config.keywords:
        query = summarize.translate_keyword(kw, config)
        if query != kw:
            log.info("키워드 번역: '%s' → '%s'", kw, query)
        for p in search_keyword(
            query,
            days_back=config.days_back,
            per_page=config.candidate_pool_per_keyword,
            mailto=config.openalex_mailto,
            display=kw,
        ):
            existing = seen.get(p.key)
            # 여러 키워드에 걸리면 더 높은 적합도 점수를 유지
            if existing is None or (p.relevance_score or 0) > (existing.relevance_score or 0):
                seen[p.key] = p
    return list(seen.values())
