"""제주 TourAPI 장소를 받아서 places 테이블에 넣는다.

    cd ai && python ../data/scripts/load_places.py --per-type 20

종류마다 per-type 곳씩. 한 곳에 상세 호출이 2번 더 들어가니
개발 계정 하루 한도(1,000회)를 넘지 않게 나눠서 받는다.
이미 있는 장소는 덮어쓴다.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg
from psycopg.types.json import Jsonb

from app.config import settings
from app.tools.tourapi import (
    CONTENT_TYPES,
    JEJU_LDONG_REGN_CD,
    area_based_list,
    detail_common,
    detail_intro,
    items_of,
    place_row,
)

COLUMNS = [
    "id", "tourapi_id", "name", "category", "cat3", "lat", "lng", "address", "phone",
    "image_url", "overview", "hours_text", "rest_text", "parking_text", "fee_text", "raw",
    "source_modified_at",
]

UPSERT = f"""
INSERT INTO places ({", ".join(COLUMNS)})
VALUES ({", ".join(f"%({c})s" for c in COLUMNS)})
ON CONFLICT (id) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS if c != "id")},
    updated_at = now()
"""


async def fetch(item: dict, sem: asyncio.Semaphore) -> dict:
    async with sem:
        cid, tid = item["contentid"], int(item["contenttypeid"])
        common = items_of(await detail_common(cid))
        intro = items_of(await detail_intro(cid, tid))
    return place_row(item, common[0] if common else None, intro[0] if intro else None)


async def main(per_type: int):
    items = []
    for type_id in CONTENT_TYPES:
        res = await area_based_list(JEJU_LDONG_REGN_CD, rows=per_type, content_type_id=type_id)
        items += items_of(res)

    sem = asyncio.Semaphore(4)
    rows = await asyncio.gather(*(fetch(i, sem) for i in items))

    with psycopg.connect(settings.database_url) as conn:
        for row in rows:
            conn.execute(UPSERT, row | {"raw": Jsonb(row["raw"])})
    print(f"{len(rows)}곳 저장 (API 호출 약 {len(CONTENT_TYPES) + len(items) * 2}회)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-type", type=int, default=20)
    asyncio.run(main(parser.parse_args().per_type))
