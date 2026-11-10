"""에이전트가 쓸 장소 목록. DB 가 있으면 places 테이블, 없으면 샘플."""

from functools import cache

from app.config import settings
from app.hours.model import Hours, Notice
from app.sample import load_places
from app.schemas.itinerary import Place

QUERY = """
SELECT id, name, lat, lng, category, indoor, hours, closed_weekdays, other_closures,
       notices, parking, typical_stay_minutes, fee, visitjeju_tags
FROM places
"""


def _row(r: tuple) -> Place:
    (pid, name, lat, lng, category, indoor, hours, weekly, other, notices,
     parking, stay, fee, tags) = r
    return Place(
        id=pid, name=name, lat=lat, lng=lng, category=category, indoor=indoor,
        hours=Hours.model_validate(hours) if hours else None,
        closed_weekdays=list(weekly) if weekly is not None else None,
        other_closures=list(other), notices=[Notice.model_validate(n) for n in notices],
        parking=parking, typical_stay_minutes=stay, fee=fee, tags=list(tags), source="tourapi",
    )


@cache
def load_db_places() -> tuple[Place, ...] | None:
    """DB 에서 읽는다. 주소가 없거나 연결이 안 되면 None."""
    if not settings.database_url:
        return None
    try:
        import psycopg

        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            rows = conn.execute(QUERY).fetchall()
    except Exception:  # noqa: BLE001  DB 가 없어도 샘플로 돌아가게
        return None
    return tuple(_row(r) for r in rows) or None


def all_places() -> tuple[Place, ...]:
    return load_db_places() or load_places()
