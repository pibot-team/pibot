"""장소 소개글과 질문을 벡터로 바꾸는 모델들. 같은 모양으로 갈아끼운다.

    get_embedder("gemini-embedding-001").embed_documents(["...", ...])

모델마다 벡터 길이(dim)가 다르다. 색인할 때 model 이름과 같이 저장한다.
"""

import time
from typing import Protocol

import numpy as np

from app.config import settings


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_queries(self, texts: list[str]) -> np.ndarray: ...


def _normalize(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class GeminiEmbedder:
    """gemini-embedding-001 / gemini-embedding-2. 무료 등급은 분당 호출 한도가 있어 재시도한다."""

    def __init__(self, name: str, dim: int = 768, batch: int = 20):
        from google import genai

        self.name = name
        self.dim = dim
        # gemini-embedding-2 는 contents 여러 개를 하나로 합쳐 벡터 1개만 돌려준다. 한 건씩 보낸다.
        self.batch = 1 if name.endswith("-2") else batch
        self.client = genai.Client(api_key=settings.gemini_api_key)

    def _embed(self, texts: list[str], task: str) -> np.ndarray:
        from google.genai import types

        out = []
        for i in range(0, len(texts), self.batch):
            chunk = texts[i : i + self.batch]
            for attempt in range(6):
                try:
                    res = self.client.models.embed_content(
                        model=self.name,
                        contents=chunk,
                        config=types.EmbedContentConfig(
                            task_type=task, output_dimensionality=self.dim
                        ),
                    )
                    if len(res.embeddings) != len(chunk):
                        raise RuntimeError(f"벡터 {len(res.embeddings)}개, 글 {len(chunk)}개")
                    out.extend(e.values for e in res.embeddings)
                    break
                except Exception as e:  # 429 등. 잠깐 쉬었다가 다시
                    # 하루 한도(PerDay)는 기다려도 풀리지 않으니 바로 멈춘다
                    if attempt == 5 or isinstance(e, RuntimeError) or "PerDay" in str(e):
                        raise
                    time.sleep(10 * (attempt + 1))
                    print(f"  재시도 {attempt + 1} ({type(e).__name__})")
        return _normalize(np.array(out))

    def embed_documents(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_queries(self, texts):
        return self._embed(texts, "RETRIEVAL_QUERY")


class BgeM3Embedder:
    """BAAI/bge-m3 (로컬, 무료). 질문·문서에 접두어를 붙이지 않는다."""

    name = "bge-m3"
    dim = 1024

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("BAAI/bge-m3")

    def _embed(self, texts):
        return _normalize(self.model.encode(texts, batch_size=8, show_progress_bar=False))

    def embed_documents(self, texts):
        return self._embed(texts)

    def embed_queries(self, texts):
        return self._embed(texts)


def get_embedder(name: str) -> Embedder:
    if name in ("gemini-embedding-001", "gemini-embedding-2"):
        return GeminiEmbedder(name)
    if name == "bge-m3":
        return BgeM3Embedder()
    raise ValueError(f"모르는 임베딩 모델: {name}")
