"""임베딩 차원 고정, 벡터 인덱스, 내부 장소 id

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    # 장소 id 를 출처와 상관없는 내부 id 로 (p000001). 출처 id 는 tourapi_id / visitjeju_id 에 있다.
    op.execute("ALTER TABLE place_search DROP CONSTRAINT place_search_place_id_fkey")
    op.execute("CREATE SEQUENCE places_id_seq START 1")
    op.execute("""
    UPDATE places p SET id = 'p' || lpad(s.rn::text, 6, '0')
    FROM (SELECT id, row_number() OVER (ORDER BY id) AS rn FROM places) s
    WHERE p.id = s.id
    """)
    op.execute(
        "SELECT CASE WHEN count(*) > 0 THEN setval('places_id_seq', count(*)) END FROM places"
    )
    op.execute("""
    ALTER TABLE places
        ALTER COLUMN id SET DEFAULT 'p' || lpad(nextval('places_id_seq')::text, 6, '0')
    """)
    op.execute("""
    ALTER TABLE place_search
        ADD CONSTRAINT place_search_place_id_fkey
        FOREIGN KEY (place_id) REFERENCES places (id) ON DELETE CASCADE ON UPDATE CASCADE
    """)

    # gemini-embedding-001 768차원, 코사인 거리 (#17)
    op.execute("ALTER TABLE place_search ALTER COLUMN embedding TYPE vector(768)")
    op.execute(
        "CREATE INDEX place_search_embedding_idx ON place_search "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade():
    op.execute("DROP INDEX place_search_embedding_idx")
    op.execute("ALTER TABLE place_search ALTER COLUMN embedding TYPE vector")
    op.execute("ALTER TABLE places ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE places_id_seq")
    # 내부 id 를 예전 tour:숫자 로 되돌리지는 않는다
