"""places 의 검색용 임베딩을 place_search 에 채운다 (이미 있는 장소는 건너뛴다).

    python scripts/reindex_places.py --dry-run
    python scripts/reindex_places.py

비짓제주 장소는 평가 때 만들어 둔 벡터(eval/rag/runs)를 옮기고, 그 밖의 장소는 Gemini 로 새로 받는다.
무료 한도에 걸리면 받은 데까지 저장하고 멈추니, 한도가 풀린 뒤 다시 돌리면 이어서 한다.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.rag.embedders import get_embedder
from app.rag.text import build_embed_text

MODEL = "gemini-embedding-001"
MODE = "name_cat_body"
RUNS = Path(__file__).resolve().parents[2] / "eval" / "rag" / "runs"
CORPUS = Path(__file__).resolve().parents[2] / "data" / "raw" / "visitjeju.json"
CHUNK = 20

TODO = """
SELECT p.id, p.name, p.category, p.overview, p.visitjeju_id
FROM places p LEFT JOIN place_search s ON s.place_id = p.id AND s.model = %s
WHERE s.place_id IS NULL
ORDER BY p.id
"""
SAVE = """
INSERT INTO place_search (place_id, embed_text, embedding, model)
VALUES (%s, %s, %s::vector, %s)
ON CONFLICT (place_id) DO UPDATE SET
    embed_text = EXCLUDED.embed_text, embedding = EXCLUDED.embedding,
    model = EXCLUDED.model, updated_at = now()
"""


def vec(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


def load_cache() -> dict[str, tuple[str, np.ndarray]]:
    """비짓제주 id -> (평가 때 쓴 글, 벡터)"""
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    docs = np.load(RUNS / f"docs_{MODEL}_{MODE}.npy")
    if len(docs) != len(corpus):
        raise SystemExit(f"벡터 {len(docs)}개, 비짓제주 {len(corpus)}곳. 평가 때 파일과 안 맞는다")
    return {
        p["id"]: (build_embed_text(p["name"], p["category"], p["intro"], p["tag"], MODE), docs[i])
        for i, p in enumerate(corpus)
    }


def main(dry_run: bool, limit: int | None) -> None:
    cache = load_cache()
    with psycopg.connect(settings.database_url) as conn:
        todo = conn.execute(TODO, (MODEL,)).fetchall()
        reuse = [r for r in todo if r[4] in cache]
        fresh = [r for r in todo if r[4] not in cache]
        print(f"채울 곳 {len(todo)}곳: 만들어 둔 벡터 옮기기 {len(reuse)}곳, 새로 받기 {len(fresh)}곳")
        if dry_run:
            return

        for pid, *_, vj_id in reuse:
            text, v = cache[vj_id]
            conn.execute(SAVE, (pid, text, vec(v), MODEL))
        conn.commit()
        print(f"옮김 {len(reuse)}곳")

        fresh = fresh[:limit] if limit else fresh
        embedder = get_embedder(MODEL)
        done = 0
        try:
            for i in range(0, len(fresh), CHUNK):
                rows = fresh[i : i + CHUNK]
                texts = [build_embed_text(n, c, o, None, MODE) for _, n, c, o, _ in rows]
                for (pid, *_), text, v in zip(rows, texts, embedder.embed_documents(texts)):
                    conn.execute(SAVE, (pid, text, vec(v), MODEL))
                conn.commit()
                done += len(rows)
        except Exception as e:  # noqa: BLE001 - 한도(429) 등 무엇이든 저장하고 멈춘다
            print(f"멈춤: {type(e).__name__} {str(e)[:100]}")
        print(f"새로 받음 {done}곳, 남음 {len(fresh) - done}곳")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 개수만 센다")
    parser.add_argument("--limit", type=int, help="새로 받을 최대 곳 수")
    args = parser.parse_args()
    main(args.dry_run, args.limit)
