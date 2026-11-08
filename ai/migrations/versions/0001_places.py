"""장소 테이블

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Spring 은 읽기만 한다. 쓰는 건 ai 쪽 수집 스크립트.
    op.execute("""
    CREATE TABLE places (
        id                   text PRIMARY KEY,
        tourapi_id           text UNIQUE,
        visitjeju_id         text UNIQUE,
        name                 text NOT NULL,
        category             text NOT NULL,
        cat3                 text,
        lat                  double precision NOT NULL,
        lng                  double precision NOT NULL,
        address              text,
        phone                text,
        image_url            text,
        overview             text,

        -- TourAPI 원문
        hours_text           text,
        rest_text            text,
        parking_text         text,
        fee_text             text,

        -- 원문을 파싱한 값. 확인 못 하면 NULL 로 둔다.
        hours                jsonb,
        closed_weekdays      smallint[] NOT NULL DEFAULT '{}',
        parking              boolean,
        fee                  integer,
        indoor               text NOT NULL DEFAULT 'unknown'
                             CHECK (indoor IN ('indoor', 'outdoor', 'mixed', 'unknown')),
        typical_stay_minutes integer,

        -- 비짓제주 (키 문제 풀리면 채움)
        visitjeju_tags       text[] NOT NULL DEFAULT '{}',
        visitjeju_intro      text,

        raw                  jsonb NOT NULL DEFAULT '{}',
        source_modified_at   timestamptz,
        updated_at           timestamptz NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX places_category_idx ON places (category)")

    # ai 만 쓴다. 벡터 차원과 인덱스는 임베딩 모델 고른 뒤 정한다 (#17).
    op.execute("""
    CREATE TABLE place_search (
        place_id   text PRIMARY KEY REFERENCES places (id) ON DELETE CASCADE,
        keywords   text[] NOT NULL DEFAULT '{}',
        embed_text text,
        embedding  vector,
        model      text,
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """)


def downgrade():
    op.execute("DROP TABLE place_search")
    op.execute("DROP TABLE places")
