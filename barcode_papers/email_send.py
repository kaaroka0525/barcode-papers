"""HTML 다이제스트 이메일 구성 + Gmail SMTP 발송 (PDF 첨부, figure 인라인)."""
import datetime as dt
import html
import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from .models import Paper

log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _render_inline(text: str) -> str:
    """**bold** 마크다운을 <b>로 변환(나머지는 escape)."""
    parts = text.split("**")
    out = []
    for i, seg in enumerate(parts):
        seg = html.escape(seg)
        out.append(f"<b>{seg}</b>" if i % 2 == 1 else seg)
    return "".join(out)


def _summary_to_html(summary: str) -> str:
    """'- **라벨**: 내용' 형식 요약을 읽기 좋은 단락으로 렌더링."""
    rows = []
    for line in summary.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.lstrip("-•* ").strip()
        rows.append(
            f"<div style='margin:7px 0;line-height:1.6;color:#333'>{_render_inline(line)}</div>"
        )
    if not rows:
        return ""
    return (
        "<div style='margin:8px 0 0 0;padding:10px 12px;background:#fafafa;"
        "border-radius:8px'>" + "".join(rows) + "</div>"
    )


def _paper_block(idx: int, p: Paper, config, cid_map: dict) -> str:
    authors = ", ".join(p.authors[:6])
    if len(p.authors) > 6:
        authors += " 외"
    year = p.year or ""
    doi_link = f"https://doi.org/{p.doi}" if p.doi else (p.landing_url or "")
    proxy = config.proxy_link(p.landing_url or doi_link)

    fig_html = ""
    for j, fig in enumerate(p.figures):
        cid = cid_map.get((idx, j))
        if cid:
            cap = f"<div style='font-size:12px;color:#888'>{html.escape(fig.caption)}</div>" if fig.caption else ""
            fig_html += (
                f"<div style='margin-top:8px'>"
                f"<img src='cid:{cid}' style='max-width:100%;border:1px solid #eee;border-radius:6px'/>"
                f"{cap}</div>"
            )

    pdf_note = (
        "<span style='color:#2e7d32'>📎 PDF 첨부됨</span>"
        if p.pdf_path
        else "<span style='color:#b26a00'>유료/비공개 — 아래 링크로 열람</span>"
    )

    links = []
    if doi_link:
        links.append(f"<a href='{html.escape(doi_link)}' style='color:#1a73e8'>원문 링크</a>")
    if proxy:
        links.append(f"<a href='{html.escape(proxy)}' style='color:#1a73e8'>한양대 프록시로 열기</a>")
    links_html = " &nbsp;·&nbsp; ".join(links)

    return f"""
    <div style="margin:0 0 26px 0;padding:16px;border:1px solid #e6e6e6;border-radius:10px">
      <div style="font-size:13px;color:#888">#{idx} · 키워드: {html.escape(p.matched_keyword)}</div>
      <div style="font-size:17px;font-weight:700;color:#111;margin:4px 0 6px 0">{html.escape(p.title)}</div>
      <div style="font-size:13px;color:#555">{html.escape(authors)} ({year})</div>
      <div style="font-size:13px;margin:6px 0">
        <b>{html.escape(p.journal)}</b>
        &nbsp;|&nbsp; <b style="color:#c2185b">{html.escape(p.if_display)}</b>
        &nbsp;|&nbsp; {pdf_note}
      </div>
      {_summary_to_html(p.summary)}
      {fig_html}
      <div style="font-size:13px;margin-top:10px">{links_html}</div>
    </div>
    """


def build_email(papers: List[Paper], config) -> MIMEMultipart:
    today = dt.date.today().isoformat()
    root = MIMEMultipart("mixed")
    root["Subject"] = f"[논문 다이제스트] {today} · IF 상위 {len(papers)}편"
    root["From"] = config.sender
    root["To"] = ", ".join(config.recipients)

    related = MIMEMultipart("related")
    root.attach(related)

    cid_map = {}
    for i, p in enumerate(papers, 1):
        for j, _fig in enumerate(p.figures):
            cid_map[(i, j)] = f"fig{i}_{j}"

    blocks = "".join(_paper_block(i, p, config, cid_map) for i, p in enumerate(papers, 1))
    kw = ", ".join(config.keywords)
    body = f"""
    <div style="font-family:-apple-system,'Apple SD Gothic Neo',Arial,sans-serif;max-width:680px;margin:0 auto">
      <h2 style="color:#111">오늘의 논문 다이제스트</h2>
      <div style="color:#666;font-size:13px;margin-bottom:18px">
        {today} · 키워드: {html.escape(kw)} · 저널 IF 기준 상위 {len(papers)}편
      </div>
      {blocks}
      <div style="color:#aaa;font-size:12px;margin-top:20px">
        IF 수치는 JCR(impact_factor 패키지) 또는 OpenAlex 2년 평균 피인용수(추정) 기준입니다.
        무료 공개본은 PDF로 첨부되며, 유료 논문은 한양대 프록시 링크로 열람하세요.
      </div>
    </div>
    """
    related.attach(MIMEText(body, "html", "utf-8"))

    # 인라인 figure
    for i, p in enumerate(papers, 1):
        for j, fig in enumerate(p.figures):
            img = MIMEImage(fig.image_bytes, _subtype=fig.ext)
            img.add_header("Content-ID", f"<{cid_map[(i, j)]}>")
            img.add_header("Content-Disposition", "inline")
            related.attach(img)

    # PDF 첨부
    for i, p in enumerate(papers, 1):
        if p.pdf_path and Path(p.pdf_path).exists():
            with open(p.pdf_path, "rb") as f:
                part = MIMEApplication(f.read(), _subtype="pdf")
            fname = f"{i:02d}_{Path(p.pdf_path).name}"
            part.add_header("Content-Disposition", "attachment", filename=fname)
            root.attach(part)

    return root


def send_email(message: MIMEMultipart, config) -> None:
    if not config.gmail_app_password:
        raise RuntimeError("GMAIL_APP_PASSWORD 가 설정되지 않았습니다 (.env 확인).")
    # 클라우드(Render 등)에서 IPv6 경로가 없어 'Network is unreachable'가 나는 것을 막기 위해
    # SMTP 연결 동안 DNS를 IPv4(AF_INET)로만 해석하도록 강제.
    import socket
    _orig_getaddrinfo = socket.getaddrinfo

    def _ipv4_only(host, *args, **kwargs):
        res = _orig_getaddrinfo(host, *args, **kwargs)
        v4 = [r for r in res if r[0] == socket.AF_INET]
        return v4 or res

    socket.getaddrinfo = _ipv4_only
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(config.sender, config.gmail_app_password)
            server.sendmail(config.sender, config.recipients, message.as_string())
    finally:
        socket.getaddrinfo = _orig_getaddrinfo
    log.info("메일 발송 완료 → %s", ", ".join(config.recipients))
