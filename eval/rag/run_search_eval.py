"""DB 검색(app/rag/search.py)을 질문 세트로 잰다 (#18).

    cd ai
    python ../eval/rag/run_search_eval.py --split dev

- 정답은 비짓제주 id 라서 places.visitjeju_id 로 내부 id 로 바꾼다.
- 정답이 비짓제주 장소에만 달려 있어서, 주 지표는 비짓제주 장소 안에서 잰 값(labeled).
  전체 장소 기준(all)은 관광공사에만 있는 장소가 정답 없음으로 세져서 낮게 나온다. 참고용.
- 질문 벡터는 한 번 받아서 runs/ 에 저장해 두고 다시 쓴다.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

import numpy as np
import psycopg
from run_eval import HERE, load_labels, load_questions

from app.config import settings
from app.rag.embedders import get_embedder
from app.rag.search import fetch_candidates

K = 5
MODEL = "gemini-embedding-001"
CACHE = HERE / "runs" / f"query_vecs_{MODEL}.json"


def query_vectors(questions: list[dict]) -> dict[str, list[float]]:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [q for q in questions if q["question"] not in cache]
    if todo:
        vecs = get_embedder(MODEL).embed_queries([q["question"] for q in todo])
        cache |= {q["question"]: v.tolist() for q, v in zip(todo, vecs, strict=True)}
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False))
    return {q["id"]: cache[q["question"]] for q in questions}


def main(split: str):
    questions = load_questions(HERE / "questions.csv", split)
    raw_labels = load_labels(HERE / "labels.csv")
    vecs = query_vectors(questions)
    with psycopg.connect(settings.database_url) as conn:
        vj = dict(conn.execute("SELECT visitjeju_id, id FROM places WHERE visitjeju_id IS NOT NULL"))
        candidates = {q["id"]: fetch_candidates(conn, vecs[q["id"]]) for q in questions}
    labeled_ids = set(vj.values())
    labels = {qid: {vj[c]: r for c, r in rel.items() if c in vj} for qid, rel in raw_labels.items()}

    p_lab, hit, p_all, per_q = [], [], [], {}
    for q in questions:
        ranked = [p.id for p, _ in sorted(candidates[q["id"]], key=lambda x: -x[1])]
        rel = labels.get(q["id"], {})
        top_lab = [i for i in ranked if i in labeled_ids][:K]
        top_all = ranked[:K]
        p_lab.append(np.mean([rel.get(i, 0) for i in top_lab]) if top_lab else 0)
        hit.append(any(rel.get(i, 0) > 0 for i in top_lab))
        p_all.append(np.mean([rel.get(i, 0) for i in top_all]) if top_all else 0)
        per_q[q["id"]] = top_lab
    print(f"[{split}] 질문 {len(questions)}개")
    print(f"  P@5 (비짓제주 장소 안) {np.mean(p_lab):.3f} · Hit@5 {np.mean(hit):.0%}")
    print(f"  P@5 (전체 장소, 참고) {np.mean(p_all):.3f}")
    (HERE / "runs" / f"search_{split}.json").write_text(json.dumps(per_q, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    main(ap.parse_args().split)
