"""영업시간·휴무·안내 형식. places.hours / closures / notices 에 그대로 들어간다."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

NoticeType = Literal["날씨", "조기 마감", "교통·예약", "변동 가능", "기타"]
WEEKDAYS = "월화수목금토일"


class HoursRule(BaseModel):
    # None 이면 해당 조건 없음 (모든 달, 모든 요일)
    months: list[int] | None = None
    weekdays: list[int] | None = None
    open: dt.time
    # open 보다 이르면 자정을 넘긴다
    close: dt.time
    # 입장 마감, 마지막 주문
    last_entry: dt.time | None = None


class Hours(BaseModel):
    status: Literal["known", "always", "unknown"]
    rules: list[HoursRule] = Field(default_factory=list)


class Closures(BaseModel):
    # 매주 쉬는 요일 (0=월). None 이면 미확인, [] 이면 매주 쉬는 날 없음
    weekly: list[int] | None = None
    # 명절, 1월 1일, 매달 2·4주 일 같은 것
    other: list[str] = Field(default_factory=list)


class Notice(BaseModel):
    type: NoticeType
    text: str


class ParsedPlace(BaseModel):
    hours: Hours
    closures: Closures
    notices: list[Notice] = Field(default_factory=list)
