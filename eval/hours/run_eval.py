"""영업시간 파서를 정답과 비교한다.

    cd ai && python ../eval/hours/run_eval.py --split dev --method rules
    cd ai && python ../eval/hours/run_eval.py --split dev --method llm:claude
    cd ai && python ../eval/hours/run_eval.py --split dev --method hybrid:ollama:qwen3:4b

method 는 rules / llm:<provider>[:<model>] / hybrid:<provider>[:<model>].
hybrid 는 규칙이 확신 없는 것만 LLM 에 넘긴다.

정답은 eval/hours/labels_{split}.csv, 원문은 로컬 DB places 에서 id 로 가져온다.
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import psycopg

from app.config import settings
from app.hours import labels, llm, rules
from app.hours.model import ParsedPlace

HERE = Path(__file__).resolve().parent
FIELDS = ["hours", "weekly", "other", "notices"]
# 100만 토큰당 달러 (입력, 출력). 모르는 모델은 토큰 수만 출력
PRICE = {"claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}


def gold(row: dict) -> ParsedPlace:
    return ParsedPlace(
        hours=labels.parse_hours(row["hours"]),
        closures=labels.parse_closures(row["closed_weekdays"], row["other_closures"]),
        notices=[{"type": t, "text": ""} for t in labels.split_list(row["notices"])],
    )


def compare(pred: ParsedPlace, ans: ParsedPlace) -> dict[str, bool]:
    return {
        "hours": pred.hours == ans.hours,
        "weekly": pred.closures.weekly == ans.closures.weekly,
        "other": sorted(pred.closures.other) == sorted(ans.closures.other),
        "notices": sorted(n.type for n in pred.notices) == sorted(n.type for n in ans.notices),
    }


def main(split: str, method: str, show: bool, limit: int | None = None):
    with open(HERE / f"labels_{split}.csv") as f:
        rows = list(csv.DictReader(f))[:limit]
    with psycopg.connect(settings.database_url) as conn:
        texts = dict(conn.execute(
            "SELECT id, (hours_text, rest_text) FROM places WHERE id = ANY(%s)",
            [[r["id"] for r in rows]],
        ).fetchall())

    kind, _, target = method.partition(":")
    provider, _, model = target.partition(":")
    if kind not in ("rules", "llm", "hybrid"):
        raise SystemExit(f"없는 방식: {method}")

    results, unsure, llm_calls, failed = [], 0, 0, 0
    tokens = {"input": 0, "output": 0}
    preds = {}
    started = time.time()
    for row in rows:
        hours_text, rest_text = texts[row["id"]]
        pred, confident = rules.parse(hours_text, rest_text)
        unsure += not confident
        if kind == "llm" or (kind == "hybrid" and not confident):
            try:
                pred, usage = llm.parse(hours_text, rest_text, provider, model or None)
                tokens = {k: tokens[k] + usage[k] for k in tokens}
            except Exception as e:  # noqa: BLE001  모델마다 예외가 달라서 실패는 미확인으로 둔다
                print(f"  ! {row['id']} {type(e).__name__}: {str(e)[:80]}")
                pred = rules.ParsedPlace(hours=rules.Hours(status="unknown"),
                                         closures=rules.Closures(weekly=None))
                failed += 1
            llm_calls += 1
        preds[row["id"]] = pred.model_dump(mode="json")
        ans = gold(row)
        ok = compare(pred, ans)
        results.append(ok)
        if show and not all(ok.values()):
            print(f"\n✗ {row['id']} {[f for f in FIELDS if not ok[f]]}")
            print("  원문:", (hours_text or "").replace("\n", " ⏎ "), "|", rest_text)
            print("  예측:", pred.model_dump(exclude_none=True))
            print("  정답:", ans.model_dump(exclude_none=True))

    n = len(results)
    print(f"\n[{split} / {method}] {n}건")
    for f in FIELDS:
        print(f"  {f:8} {sum(r[f] for r in results) / n:6.1%}")
    print(f"  전체 일치 {sum(all(r.values()) for r in results) / n:6.1%}")
    print(f"  확신 없음 {unsure}건 (규칙 기준)")
    if llm_calls:
        print(f"  LLM 호출 {llm_calls}건, 실패 {failed}건, 토큰 입력 {tokens['input']} 출력 {tokens['output']}")
        price = PRICE.get(model or {"claude": "claude-haiku-5-5"}.get(provider, ""))
        if price:
            cost = (tokens["input"] * price[0] + tokens["output"] * price[1]) / 1e6
            print(f"  비용 ${cost:.4f} (1건당 ${cost / n:.5f})")
    print(f"  걸린 시간 {time.time() - started:.0f}초")

    out = HERE / "runs" / f"{split}_{method.replace(':', '_')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(preds, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--split", default="dev")
    p.add_argument("--method", default="rules")
    p.add_argument("--show", action="store_true")
    p.add_argument("--limit", type=int, help="앞에서 N건만 (시험 삼아 돌릴 때)")
    a = p.parse_args()
    main(a.split, a.method, a.show, a.limit)
