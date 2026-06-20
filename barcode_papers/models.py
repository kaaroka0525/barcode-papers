"""파이프라인 전역에서 쓰는 논문 데이터 모델."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Figure:
    image_bytes: bytes = field(repr=False, default=b"")
    ext: str = "png"
    caption: str = ""


@dataclass
class Paper:
    title: str
    authors: List[str]
    year: Optional[int]
    journal: str
    issn: Optional[str]
    doi: Optional[str]
    landing_url: str = ""           # 출판사/원문 페이지
    pdf_url: str = ""               # OA PDF 직접 링크 (있을 때만)
    is_oa: bool = False
    abstract: str = ""
    openalex_2yr: Optional[float] = None   # OpenAlex 2년 평균 피인용수 (IF 대용)
    relevance_score: Optional[float] = None  # OpenAlex 검색 적합도 점수
    matched_keyword: str = ""

    # 후처리로 채워짐
    impact_factor: Optional[float] = None
    if_source: str = ""             # "JCR" | "OpenAlex 2yr" | ""
    summary: str = ""
    figures: List[Figure] = field(default_factory=list)
    pdf_path: Optional[str] = None  # 다운로드된 로컬 PDF 경로

    @property
    def key(self) -> str:
        """중복 판별용 안정 키 (DOI 우선, 없으면 제목)."""
        if self.doi:
            return self.doi.lower().strip()
        return "title:" + self.title.lower().strip()

    def to_dict(self) -> dict:
        """JSON 직렬화용 (figure 이미지 바이트는 제외)."""
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "issn": self.issn,
            "doi": self.doi,
            "landing_url": self.landing_url,
            "pdf_url": self.pdf_url,
            "is_oa": self.is_oa,
            "abstract": self.abstract,
            "impact_factor": self.impact_factor,
            "if_source": self.if_source,
            "summary": self.summary,
            "matched_keyword": self.matched_keyword,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        return cls(
            title=d.get("title", ""),
            authors=d.get("authors", []),
            year=d.get("year"),
            journal=d.get("journal", ""),
            issn=d.get("issn"),
            doi=d.get("doi"),
            landing_url=d.get("landing_url", ""),
            pdf_url=d.get("pdf_url", ""),
            is_oa=d.get("is_oa", False),
            abstract=d.get("abstract", ""),
            impact_factor=d.get("impact_factor"),
            if_source=d.get("if_source", ""),
            summary=d.get("summary", ""),
            matched_keyword=d.get("matched_keyword", ""),
        )

    @property
    def if_display(self) -> str:
        if self.impact_factor is None:
            return "IF 정보 없음"
        if self.if_source == "JCR":
            return f"IF {self.impact_factor:.3f} (JCR)"
        if self.if_source == "OpenAlex 2yr":
            return f"IF {self.impact_factor:.2f} (OpenAlex 추정)"
        return f"IF {self.impact_factor:.2f}"
