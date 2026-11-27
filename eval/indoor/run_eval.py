"""실내·실외 판단을 정답과 비교한다.

    cd ai && python ../eval/indoor/run_eval.py --split dev --method rules
    cd ai && python ../eval/indoor/run_eval.py --split dev --method llm
    cd ai && python ../eval/indoor/run_eval.py --split dev --method hybrid

정답은 eval/indoor/labels_{split}.csv (실제 장소 기준), 이름·태그·소개는 로컬 DB places 에서 읽는다.
실외를 실내로 잘못 보면 비 오는 날 실외로 보내게 되므로 따로 센다.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg

from app.config import settings
from app.indoor import llm, rules

HERE = Path(__file__).resolve().parent
PRICE = (0.10, 0.50)  # claude-haiku-5-5, 100만 토큰당 달러


def main(split: str, method: str, show: bool):
    with open(HERE / f"labels_{split}.csv") as f:
        gold = {r["id"]: r["indoor"] for r in csv.DictReader(f)}
    with psycopg.connect(settings.database_url) as conn:
        rows = conn.execute(
            "SELECT id, name, category, visitjeju_tags, coalesce(visitjeju_intro, overview) "
            "FROM places WHERE id = ANY(%s)", [list(gold)]).fetchall()

    right = danger = unknown = calls = 0
    tokens = [0, 0]
    preds = {}
    for pid, name, category, tags, text in rows:
        pred, confident = rules.classify(name, category, list(tags))
        if method == "llm" or (method == "hybrid" and not confident):
            pred, usage = llm.classify(name, category, list(tags), text)
            tokens = [tokens[0] + usage["input"], tokens[1] + usage["output"]]
            calls += 1
        preds[pid] = pred
        ans = gold[pid]
        right += pred == ans
        danger += ans == "outdoor" and pred in ("indoor", "mixed")
        unknown += pred == "unknown"
        if show and pred != ans:
            print(f"  ✗ {name} [{category}] 예측 {pred} / 정답 {ans}")

    n = len(rows)
    print(f"[{split} / {method}] {n}곳  정확도 {right / n:.1%}  "
          f"실외→실내 오판 {danger}  미확인 {unknown}  LLM 호출 {calls}"
          + (f"  비용 ${(tokens[0] * PRICE[0] + tokens[1] * PRICE[1]) / 1e6:.4f}" if calls else ""))
    out = HERE / "runs" / f"{split}_{method}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(preds, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev")
    p.add_argument("--method", choices=["rules", "llm", "hybrid"], default="rules")
    p.add_argument("--show", action="store_true")
    a = p.parse_args()
    main(a.split, a.method, a.show)
