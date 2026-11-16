"""제주 TourAPI 장소의 영업시간·휴무·주차·입장료 원문만 받는다.
하루 한도에 걸리면 저장하고 멈춘다. 다시 돌리면 이어서 받는다.

    cd ai && python ../data/scripts/collect_intro.py --max 900

결과는 data/raw/tour_list.json, data/raw/tour_intro.json (git에는 안 올라감).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

from app.tools.tourapi import (
    CONTENT_TYPES,
    JEJU_LDONG_REGN_CD,
    area_based_list,
    detail_intro,
    items_of,
)

RAW = Path(__file__).resolve().parents[1] / "raw"
LIST, INTRO = RAW / "tour_list.json", RAW / "tour_intro.json"


async def load_list() -> list[dict]:
    if LIST.exists():
        return json.loads(LIST.read_text())
    items = []
    for type_id in CONTENT_TYPES:
        page = 1
        while batch := items_of(await area_based_list(JEJU_LDONG_REGN_CD, page, 100, type_id)):
            items += batch
            page += 1
    RAW.mkdir(parents=True, exist_ok=True)
    LIST.write_text(json.dumps(items, ensure_ascii=False))
    return items


async def main(max_calls: int):
    items = await load_list()
    done = json.loads(INTRO.read_text()) if INTRO.exists() else {}
    todo = [i for i in items if i["contentid"] not in done][:max_calls]
    sem = asyncio.Semaphore(4)

    async def one(item):
        async with sem:
            got = items_of(await detail_intro(item["contentid"], int(item["contenttypeid"])))
            done[item["contentid"]] = got[0] if got else None

    try:
        await asyncio.gather(*(one(i) for i in todo))
    except Exception as e:  # noqa: BLE001 - 한도 초과 등은 받은 데까지 저장하고 멈춘다
        print(f"멈춤: {type(e).__name__} {str(e)[:100]}")
    INTRO.write_text(json.dumps(done, ensure_ascii=False))
    print(f"{len(done)}/{len(items)}곳 저장 (이번에 {len(todo)}곳 시도)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=900)
    asyncio.run(main(ap.parse_args().max))
