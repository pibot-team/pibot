"""places.indoor 를 채운다. 규칙이 확신하면 규칙, 아니면 Claude Haiku (eval/indoor 시험용에서 가장 정확).

    cd ai && python ../data/scripts/classify_indoor.py          # 아직 unknown 인 곳만
    cd ai && python ../data/scripts/classify_indoor.py --all    # 전부 다시
"""

import argparse
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg

from app.config import settings
from app.indoor import llm, rules

PRICE = (0.10, 0.50)  # claude-haiku-5-5, 100만 토큰당 달러


def classify(row: tuple) -> tuple[str, str, str, dict]:
    pid, name, category, tags, text = row
    value, confident = rules.classify(name, category, list(tags))
    if confident:
        return pid, value, "rules", {"input": 0, "output": 0}
    try:
        value, usage = llm.classify(name, category, list(tags), text)
        return pid, value, "llm", usage
    except Exception as e:  # noqa: BLE001  실패하면 unknown 으로 둔다
        print(f"  ! {pid} {type(e).__name__}")
        return pid, "unknown", "failed", {"input": 0, "output": 0}


def main(redo: bool, workers: int):
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            "SELECT id, name, category, visitjeju_tags, coalesce(visitjeju_intro, overview) "
            "FROM places" + ("" if redo else " WHERE indoor = 'unknown'")).fetchall()
        print(f"{len(rows)}곳")
        with ThreadPoolExecutor(workers) as pool:
            results = list(pool.map(classify, rows))
        with conn.cursor() as cur:
            cur.executemany("UPDATE places SET indoor = %s, updated_at = now() WHERE id = %s",
                            [(v, pid) for pid, v, _, _ in results])

    by = Counter(b for _, _, b, _ in results)
    values = Counter(v for _, v, _, _ in results)
    tokens = [sum(u[k] for *_, u in results) for k in ("input", "output")]
    cost = (tokens[0] * PRICE[0] + tokens[1] * PRICE[1]) / 1e6
    print(f"판단 {dict(by)}  결과 {dict(values)}  약 ${cost:.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args()
    main(a.all, a.workers)
