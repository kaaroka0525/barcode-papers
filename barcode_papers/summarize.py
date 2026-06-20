"""논문 초록을 한국어 핵심 요약으로 변환.

요약 백엔드 우선순위:
1. ANTHROPIC_API_KEY 가 있으면 Anthropic SDK 사용
2. 없으면 로컬 `claude` CLI(Claude Code) 사용  → 별도 API 키 불필요
3. 둘 다 없으면 초록 원문(잘라서)을 그대로 사용
"""
import logging
import shutil
import subprocess
import textwrap

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "당신은 연구 논문을 비전공자도 이해하도록 친절히 풀어 설명하는 어시스턴트입니다. "
    "주어진 논문 제목과 초록을 바탕으로 한국어 존댓말로, 아래 5개 항목을 정확히 이 라벨 형식으로 작성하세요. "
    "각 라벨은 줄 시작에 '- **라벨**: ' 형태로 쓰고, 전문용어는 쉬운 말로 풀어 설명합니다.\n\n"
    "- **쉽게 말하면**: 이 논문이 한마디로 무엇을 한 것인지 비전문가도 이해할 1~2문장.\n"
    "- **배경과 문제**: 어떤 상황·한계 때문에 이 연구가 필요했는지 2~3문장으로 구체적으로.\n"
    "- **무엇을 어떻게 했나**: 사용한 방법·접근을 단계가 그려지도록 쉬운 말로 2~4문장.\n"
    "- **핵심 결과**: 구체적 수치·비교 결과를 포함해 2~3문장. 숫자가 있으면 반드시 인용.\n"
    "- **왜 중요한가**: 실제 활용 가능성과 의의, 그리고 한계가 있으면 1~2문장.\n\n"
    "머리말/맺음말 없이 위 5개 불릿만 출력하세요. 초록에 없는 내용은 지어내지 마세요."
)


def _fallback(paper) -> str:
    if not paper.abstract:
        return "- (초록 정보가 없어 요약을 생성하지 못했습니다.)"
    text = textwrap.shorten(paper.abstract, width=600, placeholder=" …")
    return f"- (원문 초록) {text}"


def _user_content(paper) -> str:
    return (
        f"제목: {paper.title}\n"
        f"저널: {paper.journal}\n\n"
        f"초록:\n{paper.abstract}"
    )


def _claude_cli_path():
    return shutil.which("claude")


def _run_claude_cli(prompt: str, timeout: int = 180):
    """로컬 claude CLI로 임의 프롬프트 실행. 실패 시 None."""
    cli = _claude_cli_path()
    if not cli:
        return None
    try:
        proc = subprocess.run(
            [cli, "-p"], input=prompt, capture_output=True, text=True, timeout=timeout
        )
        out = (proc.stdout or "").strip()
        if proc.returncode == 0 and out:
            return out
        log.warning("claude CLI 실패(rc=%s): %s", proc.returncode, (proc.stderr or "")[:200])
    except Exception as e:
        log.warning("claude CLI 호출 실패: %s", e)
    return None


def _summarize_via_cli(paper, config) -> str:
    """로컬 claude CLI(Claude Code)로 요약. 별도 API 키 불필요."""
    out = _run_claude_cli(f"{SYSTEM_PROMPT}\n\n---\n{_user_content(paper)}")
    return out or _fallback(paper)


def translate_keyword(keyword: str, config) -> str:
    """한글 등 비영어 키워드를 영어 검색어로 번역. 영어면 그대로 둔다."""
    if keyword.isascii():
        return keyword
    prompt = (
        "Translate the following research topic into a concise English academic search "
        "query of 2-6 keywords. Output ONLY the query, no quotes, no explanation.\n\n"
        + keyword
    )
    text = None
    if config.has_anthropic:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            resp = client.messages.create(
                model=config.summary_model, max_tokens=40,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        except Exception as e:
            log.warning("키워드 번역 실패(API): %s", e)
    if not text:
        text = _run_claude_cli(prompt, timeout=60)
    if text:
        return text.splitlines()[0].strip().strip('"').strip()
    return keyword


def summarize_paper(paper, config) -> str:
    if not paper.abstract:
        return _fallback(paper)

    # API 키가 없으면 로컬 claude CLI로 요약 (별도 키 불필요)
    if not config.has_anthropic:
        return _summarize_via_cli(paper, config)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        resp = client.messages.create(
            model=config.summary_model,
            max_tokens=1100,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _user_content(paper)}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        out = "\n".join(parts).strip()
        return out or _fallback(paper)
    except Exception as e:
        log.warning("요약 생성 실패 [%s]: %s → 초록 원문 사용", paper.title[:40], e)
        return _fallback(paper)


def summarize_all(papers, config) -> None:
    for p in papers:
        p.summary = summarize_paper(p, config)
