"""임베딩 모델 × 색인 글 구성을 Precision@5 로 비교한다 (#17).

    cd ai
    python ../eval/rag/run_eval.py --split dev
    python ../eval/rag/run_eval.py --split test --models bge-m3 --modes name_cat_body

- 코퍼스: 비짓제주 json (eval/rag/corpus.py). 장소 글 벡터는 embed_docs.py 로 먼저 받아 둔다.
- 질문 csv: id, split, question
- 정답 csv: question_id, place_id, relevance (1 = 정답, 0.5 = 일부만 맞음). 적히지 않은 장소는 0.
- 주 지표 Precision@5 (상위 5곳의 정답 점수 평균). Hit@5(정답 1곳 이상)는 보조.
- 시험용(test)은 모델과 구성을 고른 뒤 한 번만 돌린다.
"""

import argparse
import csv
import json
import random
from itertools import combinations
from pathlib import Path

import numpy as np
from corpus import DEFAULT_CORPUS, HERE, RUNS, load_corpus, load_docs

from app.rag.embedders import get_embedder
from app.rag.text import MODES

K = 5


def load_questions(path: Path, split: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["split"] == split]


def load_labels(path: Path) -> dict[str, dict[str, float]]:
    labels: dict[str, dict[str, float]] = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            labels.setdefault(r["question_id"], {})[r["place_id"]] = float(r["relevance"])
    return labels


def bootstrap_ci(xs: list[float], n: int = 5000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(n))
    return means[int(n * 0.025)], means[int(n * 0.975)]


def sign_flip_p(diffs: list[float], n: int = 20000, seed: int = 0) -> float:
    """질문별 점수 차이의 부호를 무작위로 뒤집어 본 양측 p값 (짝지은 비교)."""
    diffs = [d for d in diffs if d != 0]
    if not diffs:
        return 1.0
    obs = abs(sum(diffs))
    rng = random.Random(seed)
    hit = sum(
        abs(sum(d if rng.random() < 0.5 else -d for d in diffs)) >= obs - 1e-12 for _ in range(n)
    )
    return hit / n


def run(model: str, mode: str, places: list[dict], questions: list[dict], labels: dict) -> dict:
    docs = load_docs(model, mode, len(places))
    qs = get_embedder(model).embed_queries([q["question"] for q in questions])
    ranks = np.argsort(-(qs @ docs.T), axis=1)[:, :K]
    ids = [p["id"] for p in places]
    per_q = {}
    for q, top in zip(questions, ranks):
        top_ids = [ids[i] for i in top]
        rel = labels.get(q["id"], {})
        scores = [rel.get(pid, 0.0) for pid in top_ids]
        per_q[q["id"]] = {"p5": sum(scores) / K, "hit": any(scores), "top": top_ids}
    return per_q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["dev", "test"])
    ap.add_argument("--questions", default=str(HERE / "questions.csv"))
    ap.add_argument("--labels", default=str(HERE / "labels.csv"))
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    ap.add_argument("--models", nargs="+", default=["gemini-embedding-001", "bge-m3"])
    ap.add_argument("--modes", nargs="+", default=list(MODES))
    args = ap.parse_args()

    places = load_corpus(args.corpus)
    names = {p["id"]: p["name"] for p in places}
    labels = load_labels(Path(args.labels))
    questions = load_questions(Path(args.questions), args.split)
    missing = [q["id"] for q in questions if q["id"] not in labels]
    if missing:
        print(f"정답 표가 없는 질문 {len(missing)}개: {', '.join(missing)}\n")
    n = len(questions)
    print(f"[{args.split}] 질문 {n}개, 장소 {len(places)}곳\n")

    results = {}
    for model in args.models:
        for mode in args.modes:
            print(f"{model} / {mode} ...")
            results[(model, mode)] = run(model, mode, places, questions, labels)

    print(f"\n{'모델':22} {'구성':16} {'P@5':>6} {'95% 구간':>12} {'Hit@5':>6}")
    for (model, mode), res in results.items():
        p5 = [r["p5"] for r in res.values()]
        lo, hi = bootstrap_ci(p5)
        hit = sum(r["hit"] for r in res.values()) / n
        print(f"{model:22} {mode:16} {sum(p5) / n:6.2f} {f'{lo:.2f}~{hi:.2f}':>12} {hit:6.0%}")

    print("\n짝지은 비교 (질문별 P@5 차이의 평균, p값)")
    for a, b in combinations(results, 2):
        diffs = [results[a][q]["p5"] - results[b][q]["p5"] for q in results[a]]
        print(f"  {a[0]}/{a[1]} - {b[0]}/{b[1]}: {sum(diffs) / n:+.3f} p={sign_flip_p(diffs):.3f}")

    RUNS.mkdir(exist_ok=True)
    (RUNS / f"{args.split}_results.json").write_text(
        json.dumps({f"{m}/{x}": r for (m, x), r in results.items()}, ensure_ascii=False, indent=1)
    )

    print("\n점수가 낮은 질문 (P@5 0.2 미만)")
    qtext = {q["id"]: q["question"] for q in questions}
    for (model, mode), res in results.items():
        low = [qid for qid, r in res.items() if r["p5"] < 0.2]
        print(f"- {model}/{mode}: {len(low)}개")
        for qid in low:
            top = ", ".join(names[i] for i in res[qid]["top"][:3])
            print(f"    {qid} {qtext[qid]} → {top}")


if __name__ == "__main__":
    main()
