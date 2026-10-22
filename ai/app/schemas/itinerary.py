"""일정 JSON 스키마.

엔진(Planner, Validator)과 여행 중 재계획, 앱 화면이 모두 이 형식을 주고받는다.
필드를 바꿀 때는 두 담당이 같이 확인한다.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Indoor = Literal["indoor", "outdoor", "mixed", "unknown"]
TravelMode = Literal["car", "transit", "walk"]


class OpeningHours(BaseModel):
    open: dt.time
    close: dt.time


class Place(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    category: str | None = None
    indoor: Indoor = "unknown"
    # None이면 영업시간 미확인. 추측해서 채우지 않는다.
    hours: OpeningHours | None = None
    # 정기 휴무 요일 (0=월 ... 6=일)
    closed_weekdays: list[int] = Field(default_factory=list)
    parking: bool | None = None
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
]


class Violation(BaseModel):
    type: ViolationType
    severity: Literal["error", "warning"] = "error"
    date: dt.date | None = None
    stop_id: str | None = None
    message: str
