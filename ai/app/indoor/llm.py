"""LLM 으로 실내·실외를 정한다. 지시문은 eval/indoor 라벨 기준과 같다."""

from typing import Literal

from pydantic import BaseModel

from app.config import settings

INSTRUCTIONS = """제주 여행 장소가 실내인지 실외인지 정한다. 비 오는 날 일정을 바꿀 때 쓴다.

기준: 실내 = 건축물 안에서 대부분 즐기는 곳.
- indoor: 박물관, 미술관, 카페, 식당, 매장, 공방·실내 체험, 사찰(법당에 들어감), 시장·오일장
- outdoor: 오름, 해변, 올레길·숲길, 정원, 공원, 동굴, 유적 터, 농장·수확 체험, 캠핑, 수상 레저
- mixed: 건물과 바깥이 둘 다 핵심인 곳 (테마파크 등)
- unknown: 이름·분류·태그·소개로 판단할 수 없음. 추측하지 않는다
"""

Indoor = Literal["indoor", "outdoor", "mixed", "unknown"]


class LLMIndoor(BaseModel):
    indoor: Indoor


def prompt(name: str, category: str, tags: list[str], text: str | None) -> str:
    return (f"{INSTRUCTIONS}\n이름: {name}\n분류: {category}\n태그: {', '.join(tags) or '(없음)'}\n"
            f"소개: {text or '(없음)'}")


def classify(name: str, category: str, tags: list[str], text: str | None,
             model: str = "claude-haiku-5-5") -> tuple[Indoor, dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    res = client.messages.parse(
        model=model, max_tokens=2000, output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt(name, category, tags, text)}],
        output_format=LLMIndoor,
    )
    if res.stop_reason == "refusal" or res.parsed_output is None:
        raise RuntimeError(f"{model} 응답 없음: {res.stop_reason}")
    return res.parsed_output.indoor, {"input": res.usage.input_tokens, "output": res.usage.output_tokens}
