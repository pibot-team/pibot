"""일정 JSON 스키마.

엔진(Planner, Validator)과 여행 중 재계획, 앱 화면이 모두 이 형식을 주고받는다.
필드를 바꿀 때는 두 담당이 같이 확인한다.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.hours.model import Hours, Notice

Indoor = Literal["indoor", "outdoor", "mixed", "unknown"]
TravelMode = Literal["car", "transit", "walk"]


class Place(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    category: str | None = None
    indoor: Indoor = "unknown"
    # 기간·요일별 영업시간 규칙. None 이면 미확인. 추측해서 채우지 않는다.
    hours: Hours | None = None
    # 매주 쉬는 요일 (0=월 ... 6=일). None 이면 미확인
    closed_weekdays: list[int] | None = Field(default_factory=list)
    # 설 당일, 추석 연휴, 명절, 1월 1일, 매달 2·4주 월 같은 휴무
    other_closures: list[str] = Field(default_factory=list)
    # 원문에 있는 알아둘 문구 (날씨, 조기 마감 등)
    notices: list[Notice] = Field(default_factory=list)
    parking: bool | None = None
    typical_stay_minutes: int | None = None
    fee: int | None = None
    tags: list[str] = Field(default_factory=list)
    source: str | None = None


class Stop(BaseModel):
    id: str
    place: Place
    start: dt.time
    end: dt.time
    # 예약한 식당·숙소처럼 재계획 때 건드리지 않는 일정
    fixed: bool = False
    cost: int = 0


class Leg(BaseModel):
    """stops[i] -> stops[i + 1] 이동."""

    mode: TravelMode = "car"
    minutes: int


class Day(BaseModel):
    date: dt.date
    stops: list[Stop]
    legs: list[Leg] = Field(default_factory=list)


class Trip(BaseModel):
    region: str
    start_date: dt.date
    end_date: dt.date
    mode: TravelMode = "car"
    budget: int | None = None
    days: list[Day]


ViolationType = Literal[
    "closed_day",
    "outside_hours",
    "hours_unknown",
    "travel_time",
    "rain_outdoor",
    "budget",
    "invalid_time",
    "missing_meal",
    "no_parking",
    # 입장 마감·마지막 주문 뒤에 도착
    "last_entry",
    # 원문 안내 (날씨, 조기 마감)와 일정이 겹침
    "notice",
]


class Violation(BaseModel):
    type: ViolationType
    severity: Literal["error", "warning"] = "error"
    date: dt.date | None = None
    stop_id: str | None = None
    message: str
