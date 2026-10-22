"""제주 TourAPI 장소를 모아서 필드별로 빈 값 비율을 출력한다.

    cd ai && python ../data/scripts/collect_tourapi.py

결과는 data/raw/jeju_places.json 에 저장 (git에는 안 올라감).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

from app.tools.tourapi import JEJU_AREA_CODE, area_based_list

OUT = Path(__file__).resolve().parents[1] / "raw" / "jeju_places.json"


def items_of(res: dict) -> list[dict]:
    items = res["response"]["body"]["items"]
    if not items:
        return []
    item = items["item"]
    return item if isinstance(item, list) else [item]


async def main():
    places, page = [], 1
    while True:
        batch = items_of(await area_based_list(JEJU_AREA_CODE, page=page, rows=100))
        if not batch:
            break
        places += batch
        page += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(places, ensure_ascii=False, indent=2))
    print(f"{len(places)}곳 저장 -> {OUT}")

    fields = sorted({k for p in places for k in p})
    for f in fields:
        empty = sum(1 for p in places if not p.get(f))
        print(f"{f:20} 빈 값 {empty / len(places):6.1%}")


if __name__ == "__main__":
    asyncio.run(main())
