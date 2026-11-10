"""places 의 영업시간·휴무 원문을 파싱해서 hours, closed_weekdays, other_closures, notices 를 채운다.

    cd ai && python ../data/scripts/parse_places.py            # 아직 안 한 곳만
    cd ai && python ../data/scripts/parse_places.py --all      # 전부 다시

기본은 Claude Haiku 5.5 (eval/hours 시험용에서 가장 정확). 실패하면 규칙 파서 결과를 넣는다.
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg
from psycopg.types.json import Jsonb

from app.config import settings
from app.hours import llm, rules

MODEL = "claude-haiku-5-5"
# 100만 토큰당 달러 (입력, 출력)
PRICE = (0.10, 0.50)

UPDATE = """
UPDATE places SET
    hours = %(hours)s,
    closed_weekdays = %(weekly)s,
    other_closures = %(other)s,
    notices = %(notices)s,
    parsed_by = %(by)s,
    parsed_at = now()
WHERE id = %(id)s
"""


def parse_one(row: tuple) -> dict:
    pid, hours_text, rest_text = row
    usage = {"input": 0, "output": 0}
    try:
        parsed, usage = llm.parse(hours_text, rest_text, "claude", MODEL)
        by = MODEL
    except Exception as e:  # noqa: BLE001  API 장애 때는 규칙 파서로 대신한다
        print(f"  ! {pid} {type(e).__name__}, 규칙으로 대신")
        parsed, _ = rules.parse(hours_text, rest_text)
        by = "rules"
    return {
        "id": pid,
        "hours": Jsonb(parsed.hours.model_dump(mode="json")),
        "weekly": parsed.closures.weekly,
        "other": parsed.closures.other,
        "notices": Jsonb([n.model_dump() for n in parsed.notices]),
        "by": by,
        "usage": usage,
    }


def main(redo: bool, workers: int):
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            "SELECT id, hours_text, rest_text FROM places"
            " WHERE (hours_text IS NOT NULL OR rest_text IS NOT NULL)"
            + ("" if redo else " AND parsed_by IS NULL")
        ).fetchall()
        print(f"{len(rows)}곳 파싱")
        with ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(parse_one, rows))
        for r in results:
            conn.execute(UPDATE, r)

    tokens = [sum(r["usage"][k] for r in results) for k in ("input", "output")]
    cost = (tokens[0] * PRICE[0] + tokens[1] * PRICE[1]) / 1e6
    fallback = sum(r["by"] == "rules" for r in results)
    print(f"완료. 규칙으로 대신 {fallback}곳, 토큰 {tokens[0]}/{tokens[1]}, 약 ${cost:.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="이미 파싱한 곳도 다시")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    main(a.all, a.workers)
