"""저널 Impact Factor 조회.

1순위: impact_factor 패키지(내장 JCR DB) — 실제 IF 수치
2순위: OpenAlex source 의 2yr_mean_citedness — IF 동일 개념의 공개 지표
"""
import logging
from typing import Optional, Tuple

import requests

log = logging.getLogger(__name__)

# impact_factor 가 echo=True 엔진을 import 시점에 만들므로, 먼저 로그를 잠재운다.
for _name in ("sqlalchemy", "sqlalchemy.engine", "sqlalchemy.engine.Engine"):
    logging.getLogger(_name).setLevel(logging.WARNING)

OPENALEX_SOURCES = "https://api.openalex.org/sources"

# impact_factor 패키지는 선택 사항. 없으면 OpenAlex 지표만 사용.
try:
    from impact_factor.core import Factor

    _factor = Factor()
    _HAS_IF_PKG = True
except Exception as e:  # pragma: no cover
    _factor = None
    _HAS_IF_PKG = False
    log.info("impact_factor 패키지 미사용(%s) → OpenAlex 지표로 대체", e)

_jcr_cache = {}
_oa_cache = {}


def _jcr_lookup(journal: str, issn: Optional[str]) -> Optional[float]:
    if not _HAS_IF_PKG or not journal:
        return None
    cache_key = (journal or "").lower()
    if cache_key in _jcr_cache:
        return _jcr_cache[cache_key]
    value = None
    try:
        rows = _factor.search(journal) or []
        if not rows and issn:
            rows = _factor.search(issn) or []
        if rows:
            raw = rows[0].get("factor") or rows[0].get("jcr") or rows[0].get("if")
            value = float(raw) if raw not in (None, "", "N/A") else None
    except Exception as e:
        log.debug("JCR 조회 실패 [%s]: %s", journal, e)
    _jcr_cache[cache_key] = value
    return value


def _openalex_2yr(issn: Optional[str], journal: str, mailto: str) -> Optional[float]:
    cache_key = (issn or journal or "").lower()
    if not cache_key:
        return None
    if cache_key in _oa_cache:
        return _oa_cache[cache_key]

    value = None
    try:
        if issn:
            params = {"filter": f"issn:{issn}", "per_page": 1}
        else:
            params = {"search": journal, "per_page": 1}
        if mailto:
            params["mailto"] = mailto
        resp = requests.get(OPENALEX_SOURCES, params=params, timeout=20)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            stats = results[0].get("summary_stats") or {}
            v = stats.get("2yr_mean_citedness")
            value = float(v) if v is not None else None
    except Exception as e:
        log.debug("OpenAlex source 조회 실패 [%s]: %s", journal, e)
    _oa_cache[cache_key] = value
    return value


def resolve_impact_factor(journal: str, issn: Optional[str], mailto: str) -> Tuple[Optional[float], str]:
    jcr = _jcr_lookup(journal, issn)
    if jcr is not None:
        return jcr, "JCR"
    oa = _openalex_2yr(issn, journal, mailto)
    if oa is not None:
        return oa, "OpenAlex 2yr"
    return None, ""


def annotate(papers, config) -> None:
    """각 Paper 에 impact_factor / if_source 를 채운다."""
    for p in papers:
        value, src = resolve_impact_factor(p.journal, p.issn, config.openalex_mailto)
        p.impact_factor = value
        p.if_source = src
