"""평가용 코퍼스(비짓제주 json)와 장소 글 임베딩 캐시. 한도에 걸리면 저장하고 멈췄다가 이어서 받는다."""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai"))

from app.rag.embedders import get_embedder
from app.rag.text import build_embed_text

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
DEFAULT_CORPUS = RUNS / "vj_corpus.json"
CHUNK = 20


def load_corpus(path: Path = DEFAULT_CORPUS) -> list[dict]:
    """id, name, category, intro, tag 가 있는 장소 목록."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def doc_cache(model: str, mode: str) -> Path:
    return RUNS / f"docs_{model}_{mode}.npy"


def load_docs(model: str, mode: str, n: int) -> np.ndarray:
    path = doc_cache(model, mode)
    if not path.exists():
        raise SystemExit(
            f"{path.name} 이 없다. 먼저: python embed_docs.py --model {model} --mode {mode}"
        )
    docs = np.load(path)
    if len(docs) != n:
        raise SystemExit(
            f"{path.name}: 벡터 {len(docs)}개, 장소 {n}곳. 아직 덜 받았거나 코퍼스가 바뀜"
        )
    return docs


def embed_docs(corpus: list[dict], model: str, mode: str) -> None:
    """캐시가 다 찰 때까지 이어서 받는다. 도중에 멈추면 .partial.npy 에 저장."""
    texts = [build_embed_text(p["name"], p["category"], p["intro"], p["tag"], mode) for p in corpus]
    final = doc_cache(model, mode)
    part = final.with_suffix(".partial.npy")
    final.parent.mkdir(exist_ok=True)
    if final.exists() and len(np.load(final)) == len(texts):
        print("이미 다 받았다")
        return
    done = np.load(part) if part.exists() else None
    chunks = [done] if done is not None else []
    have = lambda: sum(len(c) for c in chunks)
    start = have()
    emb = get_embedder(model)
    try:
        while have() < len(texts):
            i = have()
            chunks.append(emb.embed_documents(texts[i : i + CHUNK]))
            if (i // CHUNK) % 10 == 0:
                print(f"  {i + CHUNK}/{len(texts)}", flush=True)
    except Exception as e:  # noqa: BLE001 - 한도(429) 등 무엇이든 저장하고 멈춘다
        print(f"멈춤: {type(e).__name__} {str(e)[:100]}")
    if have() >= len(texts):
        np.save(final, np.concatenate(chunks))
        part.unlink(missing_ok=True)
        print(f"완료 {have()}건")
    else:
        if chunks:
            np.save(part, np.concatenate(chunks))
        print(f"저장 {have()}/{len(texts)} (이번에 {have() - start})")
