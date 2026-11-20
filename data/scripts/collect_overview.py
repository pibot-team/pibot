"""TourAPI 장소의 소개글(overview)을 받는다. 비짓제주에 없는 장소만.
한도에 걸리면 저장하고 멈춘다. 다시 돌리면 이어서 받는다.

    cd ai && python ../data/scripts/collect_overview.py --max 900

받을 장소 id 는 data/raw/tour_need_overview.json (contentid 목록).
결과는 data/raw/tour_overview.json (git에는 안 올라감).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

from app.tools.tourapi import clean_text, detail_common, items_of

RAW = Path(__file__).resolve().parents[1] / "raw"
NEED, OUT = RAW / "tour_need_overview.json", RAW / "tour_overview.json"


async def main(max_calls: int):
    need = json.loads(NEED.read_text())
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    todo = [i for i in need if i not in done][:max_calls]
    sem = asyncio.Semaphore(4)

    async def one(cid):
        async with sem:
            got = items_of(await detail_common(cid))
            done[cid] = clean_text(got[0].get("overview")) if got else None

    try:
        await asyncio.gather(*(one(i) for i in todo))
    except Exception as e:  # noqa: BLE001 - 한도 초과 등은 받은 데까지 저장하고 멈춘다
        print(f"멈춤: {type(e).__name__} {str(e)[:100]}")
    OUT.write_text(json.dumps(done, ensure_ascii=False))
    print(f"{len(done)}/{len(need)}곳 저장 (이번에 {len(todo)}곳 시도)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=900)
    asyncio.run(main(ap.parse_args().max))
