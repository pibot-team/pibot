"""LLM 으로 영업시간·휴무·안내를 읽는다. 모델마다 호출만 다르고 지시문과 검증은 같다.

LLM 이 원문에 없는 시각을 지어내면 그 규칙은 버리고 미확인으로 둔다.
"""

import datetime as dt
import json
import re
import time
from typing import Literal

import httpx
from pydantic import BaseModel

from app.config import settings
from app.hours.model import Closures, Hours, HoursRule, Notice, NoticeType, ParsedPlace

INSTRUCTIONS = """제주 관광지의 이용시간·휴무 원문을 정해진 형식으로 옮긴다.

규칙
1. 원문에 없는 건 쓰지 않는다. 상식으로 채우지 않는다.
2. 전화문의만 있으면 영업시간은 unknown.
3. 시각과 전화문의가 같이 있으면 시각을 쓴다.
4. 입실/퇴실, 투어 출발 시각처럼 영업시간이 아니면 unknown.
5. 자정을 넘기면 그대로 (18:00~02:00).
6. 브레이크타임·휴게시간·준비시간은 영업시간에 넣지 않는다.
7. 명절·1월 1일만 쉬면 weekly_closed 는 빈 목록, other_closures 에 적는다.
   설·추석은 당일과 연휴를 나눈다. "설·추석 연휴" 는 "설 연휴", "추석 연휴".
   연휴라고 안 하면 당일. 원문이 그냥 "명절" 이면 "명절".
8. 우천·기상에 따른 휴무는 휴무가 아니라 안내(날씨)다.
9. 구역마다 시간이 다르면 대표 공간(전시실, 본관 등) 기준.

형식
- hours_status: known(시각 있음) / always(상시 개방) / unknown
- rules: 기간(months)·요일(weekdays)마다 하나. 해당 없으면 null.
  weekdays 는 원문에 요일마다 시간이 따로 적혀 있을 때만 쓴다.
  휴무일을 빼서 요일을 만들지 않는다 (휴무는 weekly_closed 에만).
  months 는 1~12, weekdays 는 0=월 ... 6=일. "3월~10월" 은 [3,...,10], "토~월" 은 [5,6,0].
- 시각은 "HH:MM". last_entry 는 입장 마감·마지막 주문. "30분 전 입장 마감" 이면 닫는 시각에서 뺀다.
- weekly_closed: 매주 쉬는 요일. 주말은 [5,6].
  매주 쉬는 요일이 없다고 읽히면 [] (연중무휴, 명절만 쉼, 1월 1일만 쉼 등).
  휴무 원문이 없거나 전화문의뿐이라 알 수 없으면 null.
- other_closures: 이 표현만 쓴다 -> "설 당일", "설 연휴", "추석 당일", "추석 연휴", "명절",
  "법정공휴일", "1월 1일" 같은 "M월 D일",
  "매달 2·4주 월" 같은 "매달 N주 요일".
- notices: 원문에 있는 알아둘 문구. type 은 날씨 / 조기 마감 / 교통·예약 / 변동 가능 / 기타.
  text 는 원문 문장 그대로. "자세한 사항은 전화문의" 처럼 어디에나 붙는 문구는 넣지 않는다.
"""


class LLMRule(BaseModel):
    months: list[int] | None
    weekdays: list[int] | None
    open: str
    close: str
    last_entry: str | None


class LLMNotice(BaseModel):
    type: NoticeType
    text: str


class LLMOutput(BaseModel):
    hours_status: Literal["known", "always", "unknown"]
    rules: list[LLMRule]
    weekly_closed: list[int] | None
    other_closures: list[str]
    notices: list[LLMNotice]


def prompt(hours_text: str | None, rest_text: str | None) -> str:
    return f"{INSTRUCTIONS}\n이용시간 원문:\n{hours_text or '(없음)'}\n\n휴무 원문:\n{rest_text or '(없음)'}"


def _time(value: str) -> dt.time:
    h, m = value.strip().split(":")
    return dt.time(int(h) % 24, int(m))


def _in_text(value: str, text: str) -> bool:
    h, m = value.strip().split(":")
    # "19:3014:00" 처럼 시간이 붙어 있는 원문이 있어서 뒤쪽은 막지 않는다
    return re.search(rf"(?<!\d)0?{int(h)}:{m}", text) is not None


def to_parsed(out: LLMOutput, hours_text: str | None) -> ParsedPlace:
    """LLM 출력을 검증해서 ParsedPlace 로. 원문에 없는 시각이 나오면 영업시간은 미확인."""
    source = hours_text or ""
    hours = Hours(status=out.hours_status)
    if out.hours_status == "known":
        made_up = any(not _in_text(v, source) for r in out.rules for v in (r.open, r.close))
        if made_up or not out.rules:
            hours = Hours(status="unknown")
        else:
            hours.rules = [
                HoursRule(months=r.months, weekdays=r.weekdays, open=_time(r.open),
                          close=_time(r.close),
                          last_entry=_time(r.last_entry) if r.last_entry else None)
                for r in out.rules
            ]
    weekly = sorted(set(out.weekly_closed)) if out.weekly_closed is not None else None
    return ParsedPlace(
        hours=hours,
        closures=Closures(weekly=weekly, other=sorted(set(out.other_closures))),
        notices=[Notice(type=n.type, text=n.text) for n in out.notices],
    )


# ---------------------------------------------------------------- 모델별 호출


def ask_claude(text: str, model: str = "claude-haiku-5-5") -> tuple[LLMOutput, dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    res = client.messages.parse(
        model=model,
        max_tokens=4000,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": text}],
        output_format=LLMOutput,
    )
    if res.stop_reason == "refusal" or res.parsed_output is None:
        raise RuntimeError(f"{model} 응답 없음: {res.stop_reason}")
    usage = {"input": res.usage.input_tokens, "output": res.usage.output_tokens}
    return res.parsed_output, usage


def ask_gemini(text: str, model: str = "gemini-3.5-flash-lite") -> tuple[LLMOutput, dict]:
    from google import genai
    from google.genai import errors

    client = genai.Client(api_key=settings.gemini_api_key)
    # 무료 등급은 분당 15회. 한도(429)나 일시 장애(503)면 기다렸다가 다시 시도
    for attempt in range(4):
        try:
            res = client.models.generate_content(
                model=model,
                contents=text,
                config={"response_mime_type": "application/json", "response_schema": LLMOutput},
            )
            break
        except errors.APIError as e:
            if e.code not in (429, 503) or attempt == 3:
                raise
            time.sleep(30 if e.code == 429 else 5)
    meta = res.usage_metadata
    usage = {"input": meta.prompt_token_count, "output": meta.candidates_token_count}
    return LLMOutput.model_validate_json(res.text), usage


def ask_ollama(text: str, model: str = "qwen3:4b") -> tuple[LLMOutput, dict]:
    res = httpx.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "format": LLMOutput.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=300,
    )
    res.raise_for_status()
    body = res.json()
    usage = {"input": body.get("prompt_eval_count", 0), "output": body.get("eval_count", 0)}
    return LLMOutput.model_validate(json.loads(body["message"]["content"])), usage


ASK = {"claude": ask_claude, "gemini": ask_gemini, "ollama": ask_ollama}


def parse(hours_text: str | None, rest_text: str | None, provider: str,
          model: str | None = None) -> tuple[ParsedPlace, dict]:
    ask = ASK[provider]
    out, usage = ask(prompt(hours_text, rest_text), **({"model": model} if model else {}))
    return to_parsed(out, hours_text), usage
