"""OA PDF 다운로드 + PyMuPDF로 핵심 figure 이미지 추출."""
import logging
import re
from pathlib import Path
from typing import List, Optional

import requests

from .config import PDF_DIR
from .models import Figure

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

_CAPTION_RE = re.compile(r"(fig(?:ure)?\.?\s*\d+|table\s*\d+)", re.IGNORECASE)


def figures_supported() -> bool:
    """PyMuPDF가 있어야 figure 추출 가능(서버리스엔 보통 없음)."""
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _safe_name(paper) -> str:
    base = paper.doi or paper.title
    return re.sub(r"[^\w\-]+", "_", base)[:80] or "paper"


def download_pdf(paper, dest_dir: Path = PDF_DIR) -> Optional[str]:
    """OA PDF가 있으면 내려받아 로컬 경로 반환. 실패 시 None."""
    if not paper.pdf_url:
        return None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    dest = dest_dir / (_safe_name(paper) + ".pdf")
    try:
        resp = requests.get(paper.pdf_url, headers=_HEADERS, timeout=(4, 10), stream=True)
        resp.raise_for_status()
        ctype = resp.headers.get("Content-Type", "")
        if "pdf" not in ctype and not paper.pdf_url.lower().endswith(".pdf"):
            # HTML 랜딩 페이지가 온 경우 등은 건너뜀
            log.debug("PDF 아님 (%s) [%s]", ctype, paper.pdf_url)
            return None
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        if dest.stat().st_size < 1024:
            dest.unlink(missing_ok=True)
            return None
        paper.pdf_path = str(dest)
        return str(dest)
    except requests.RequestException as e:
        log.info("PDF 다운로드 실패 [%s]: %s", paper.title[:40], e)
        return None


def extract_figures(pdf_path: str, max_figures: int = 3) -> List[Figure]:
    """본문에서 큰 이미지 위주로 figure 후보를 추출(휴리스틱)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        log.warning("PyMuPDF 미설치 → figure 추출 생략")
        return []

    figures: List[Figure] = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log.info("PDF 열기 실패: %s", e)
        return []

    try:
        for page in doc:
            page_text = page.get_text()
            captions = _CAPTION_RE.findall(page_text or "")
            caption = captions[0] if captions else ""
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.width < 300 or pix.height < 200:
                        continue  # 아이콘/로고 등 작은 이미지 제외
                    if pix.n - pix.alpha >= 4:  # CMYK → RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    figures.append(
                        Figure(image_bytes=pix.tobytes("png"), ext="png", caption=caption)
                    )
                    pix = None
                except Exception:
                    continue
                if len(figures) >= max_figures:
                    return figures
    finally:
        doc.close()
    return figures
