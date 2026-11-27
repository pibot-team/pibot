"""DB 장소 검색: 조건으로 거르고 뜻이 가까운 순 (#18).

이름 일치 가산점도 시험했지만 dev 질문에서 P@5 가 떨어져서(0.861 → 0.782, 가산점 0.1) 넣지 않았다.
"""

from app.agent.search import filter_and_rank
from app.places import COLUMNS, _row
from app.schemas import tools as t
from app.schemas.itinerary import Place

# 벡터로 먼저 가져올 후보 수. 조건으로 거른 뒤 limit 만큼 돌려준다
POOL = 200

_SELECT = (f"SELECT {', '.join('p.' + c for c in COLUMNS)}, 1 - (s.embedding <=> %(q)s::vector) "
           "FROM place_search s JOIN places p ON p.id = s.place_id WHERE s.embedding IS NOT NULL "
           "ORDER BY s.embedding <=> %(q)s::vector LIMIT %(n)s")


def fetch_candidates(conn, query_vec, pool: int = POOL) -> list[tuple[Place, float]]:
    vec = "[" + ",".join(f"{x:.6f}" for x in query_vec) + "]"
    rows = conn.execute(_SELECT, {"q": vec, "n": pool}).fetchall()
    return [(_row(r[:-1]), float(r[-1])) for r in rows]


def search(req: t.SearchPlacesIn, conn, embedder) -> t.SearchPlacesOut:
    query_vec = embedder.embed_queries([req.query])[0]
    return filter_and_rank(fetch_candidates(conn, query_vec), req)
