# 개발용 제주 샘플 장소. 좌표·영업시간·요금은 대략값, "샘플"로 시작하는 곳은 가짜

import json
from functools import cache
from pathlib import Path

from app.schemas.itinerary import Place

PATH = Path(__file__).with_name("jeju_places.json")


@cache
def load_places() -> tuple[Place, ...]:
    raw = json.loads(PATH.read_text())
    return tuple(Place.model_validate(p | {"source": "sample"}) for p in raw)


def place_by_id(place_id: str) -> Place | None:
    return next((p for p in load_places() if p.id == place_id), None)
