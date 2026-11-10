"""시험용 결과를 정리한다: 정확도와 95% 신뢰구간, 방식끼리 McNemar 검정, 틀린 유형.

    cd ai && python ../eval/hours/compare.py --split test

run_eval.py 가 남긴 eval/hours/runs/{split}_{method}.json 을 읽는다.
"""

import argparse
import csv
import json
import math
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_eval import FIELDS, compare, gold

from app.hours.model import ParsedPlace

HERE = Path(__file__).resolve().parent


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return center - half, center + half


def mcnemar(b: int, c: int) -> float:
    """한쪽만 맞힌 건수 b, c 로 정확(이항) McNemar p값."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main(split: str):
    with open(HERE / f"labels_{split}.csv") as f:
        answers = {r["id"]: gold(r) for r in csv.DictReader(f)}
    runs = {}
    for path in sorted((HERE / "runs").glob(f"{split}_*.json")):
        preds = json.loads(path.read_text())
        runs[path.stem.removeprefix(f"{split}_")] = {
            pid: compare(ParsedPlace.model_validate(p), answers[pid]) for pid, p in preds.items()
        }

    n = len(answers)
    print(f"[{split}] {n}건\n")
    print(f"{'방식':16} {'전체 일치':>9} {'95% 구간':>15} " + " ".join(f"{f:>8}" for f in FIELDS))
    for name, res in runs.items():
        k = sum(all(r.values()) for r in res.values())
        lo, hi = wilson(k, n)
        fields = " ".join(f"{sum(r[f] for r in res.values()) / n:8.0%}" for f in FIELDS)
        print(f"{name:16} {k / n:9.0%} {f'{lo:.0%}~{hi:.0%}':>15} {fields}")

    print("\nMcNemar (한쪽만 맞힌 건수, p값)")
    for a, b in combinations(runs, 2):
        only_a = sum(all(runs[a][p].values()) and not all(runs[b][p].values()) for p in answers)
        only_b = sum(all(runs[b][p].values()) and not all(runs[a][p].values()) for p in answers)
        print(f"  {a} vs {b}: {only_a} / {only_b}, p={mcnemar(only_a, only_b):.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="test")
    main(p.parse_args().split)
