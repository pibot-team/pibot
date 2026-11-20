"""TourAPI 와 비짓제주 장소를 합쳐서 places 테이블에 넣는다.

    cd ai && python ../data/scripts/build_places.py --dry-run
    cd ai && python ../data/scripts/build_places.py

필요한 파일 (data/raw/): tour_list.json, tour_intro.json, tour_overview.json, visitjeju.json
같은 장소는 이름이 같거나 한쪽이 다른 쪽에 들어가고, 거리 150m 이내, 종류가 맞을 때로 본다.
합친 장소는 TourAPI 의 영업시간·주차 등에 비짓제주 소개글·태그를 붙인다.
이미 있는 장소는 덮어쓴다. id 는 DB 가 붙이고, 파싱해 둔 영업시간 칸은 건드리지 않는다.
"""

import argparse
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg
from psycopg.types.json import Jsonb

from app.config import settings
from app.tools.tourapi import place_row

RAW = Path(__file__).resolve().parents[1] / "raw"
MAX_DIST_M = 150
# 비짓제주 종류 -> 같은 곳으로 볼 수 있는 TourAPI contenttypeid
SAME_KIND = {"음식점": {39}, "쇼핑": {38}, "관광지": {12, 14, 28}}

TOUR_COLUMNS = [
    "tourapi_id", "visitjeju_id", "name", "category", "cat3", "lat", "lng", "address", "phone",
    "image_url", "overview", "hours_text", "rest_text", "parking_text", "fee_text",
    "visitjeju_tags", "visitjeju_intro", "raw", "source_modified_at",
]
VJ_COLUMNS = [
    "visitjeju_id", "name", "category", "lat", "lng", "overview", "visitjeju_tags",
    "visitjeju_intro", "raw",
]


def upsert_sql(columns: list[str], key: str) -> str:
    return f"""
INSERT INTO places ({", ".join(columns)})
VALUES ({", ".join(f"%({c})s" for c in columns)})
ON CONFLICT ({key}) DO UPDATE SET
    {", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)},
    updated_at = now()
"""


def norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", s.lower())


def meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = (a[0] - b[0]) * 111000
    dx = (a[1] - b[1]) * 111000 * math.cos(math.radians(33.4))
    return math.hypot(dx, dy)


def match(tour: list[dict], vj: list[dict]) -> dict[str, str]:
    """TourAPI id -> 비짓제주 id. 한쪽에 하나씩만 짝지어서 가까운 것부터 정한다."""
    grid = defaultdict(list)
    for t in tour:
        lat, lng = float(t["mapy"]), float(t["mapx"])
        grid[int(lat / 0.005), int(lng / 0.005)].append((t, lat, lng))

    pairs = []
    for v in vj:
        kx, ky = int(v["lat"] / 0.005), int(v["lng"] / 0.005)
        nv = norm(v["name"])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for t, lat, lng in grid.get((kx + dx, ky + dy), []):
                    if int(t["contenttypeid"]) not in SAME_KIND[v["category"]]:
                        continue
                    dist = meters((v["lat"], v["lng"]), (lat, lng))
                    if dist > MAX_DIST_M:
                        continue
                    nt = norm(t["title"])
                    exact = nt == nv
                    similar = min(len(nt), len(nv)) >= 3 and (nt in nv or nv in nt)
                    if exact or similar:
                        pairs.append((not exact, dist, t["contentid"], v["id"]))

    linked, used_vj = {}, set()
    for _, _, tour_id, vj_id in sorted(pairs):
        if tour_id not in linked and vj_id not in used_vj:
            linked[tour_id] = vj_id
            used_vj.add(vj_id)
    return linked


def tags_of(v: dict | None) -> list[str]:
    return [x.strip() for x in v["tag"].split(",") if x.strip()] if v and v.get("tag") else []


def build_rows() -> tuple[list[dict], list[dict], int]:
    tour = json.loads((RAW / "tour_list.json").read_text(encoding="utf-8"))
    intros = json.loads((RAW / "tour_intro.json").read_text(encoding="utf-8"))
    overviews = json.loads((RAW / "tour_overview.json").read_text(encoding="utf-8"))
    vj_all = json.loads((RAW / "visitjeju.json").read_text(encoding="utf-8"))
    # 좌표가 없으면 이동시간을 못 구하고 칸도 NOT NULL 이라 넣지 않는다
    vj = [v for v in vj_all if v["lat"] is not None and v["lng"] is not None]
    vj_by_id = {v["id"]: v for v in vj}
    linked = match(tour, vj)

    tour_rows = []
    for item in tour:
        cid = item["contentid"]
        v = vj_by_id.get(linked.get(cid))
        row = place_row(item, {"overview": overviews.get(cid)}, intros.get(cid))
        row["overview"] = row["overview"] or (v["intro"] if v else None)
        row["visitjeju_id"] = v["id"] if v else None
        row["visitjeju_tags"] = tags_of(v)
        row["visitjeju_intro"] = v["intro"] if v else None
        if v:
            row["raw"] = row["raw"] | {"visitjeju": v}
        tour_rows.append(row)

    only = set(vj_by_id) - set(linked.values())
    vj_rows = [
        {
            "visitjeju_id": v["id"], "name": v["name"], "category": v["category"],
            "lat": v["lat"], "lng": v["lng"], "overview": v["intro"],
            "visitjeju_tags": tags_of(v), "visitjeju_intro": v["intro"],
            "raw": {"visitjeju": v},
        }
        for v in vj if v["id"] in only
    ]
    return tour_rows, vj_rows, len(vj_all) - len(vj)


def main(dry_run: bool) -> None:
    tour_rows, vj_rows, no_coord = build_rows()
    merged = sum(1 for r in tour_rows if r["visitjeju_id"])
    print(f"TourAPI {len(tour_rows)}곳 (비짓제주와 합침 {merged}곳), 비짓제주만 {len(vj_rows)}곳, 좌표 없어 뺀 곳 {no_coord}곳")
    if dry_run:
        return
    with psycopg.connect(settings.database_url) as conn:
        for row in tour_rows:
            conn.execute(upsert_sql(TOUR_COLUMNS, "tourapi_id"), row | {"raw": Jsonb(row["raw"])})
        for row in vj_rows:
            conn.execute(upsert_sql(VJ_COLUMNS, "visitjeju_id"), row | {"raw": Jsonb(row["raw"])})
    print("저장 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="DB에 넣지 않고 개수만 센다")
    main(parser.parse_args().dry_run)
