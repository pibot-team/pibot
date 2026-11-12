"""영업시간 파싱 결과 칸

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    # NULL 이면 휴무 미확인, {} 이면 매주 쉬는 날 없음
    op.execute("ALTER TABLE places ALTER COLUMN closed_weekdays DROP NOT NULL")
    op.execute("ALTER TABLE places ALTER COLUMN closed_weekdays DROP DEFAULT")
    op.execute("UPDATE places SET closed_weekdays = NULL WHERE hours IS NULL")
    op.execute("""
    ALTER TABLE places
        -- 명절, 1월 1일, 매달 2·4주 일 처럼 요일로 안 되는 휴무
        ADD COLUMN other_closures text[] NOT NULL DEFAULT '{}',
        -- [{"type": "날씨", "text": "우천시 휴무"}]
        ADD COLUMN notices jsonb NOT NULL DEFAULT '[]',
        -- 어떤 방식으로 파싱했는지 (rules, rules+llm 등). NULL 이면 아직 안 함
        ADD COLUMN parsed_by text,
        ADD COLUMN parsed_at timestamptz
    """)


def downgrade():
    op.execute("""
    ALTER TABLE places
        DROP COLUMN parsed_at,
        DROP COLUMN parsed_by,
        DROP COLUMN notices,
        DROP COLUMN other_closures
    """)
    op.execute("UPDATE places SET closed_weekdays = '{}' WHERE closed_weekdays IS NULL")
    op.execute("ALTER TABLE places ALTER COLUMN closed_weekdays SET DEFAULT '{}'")
    op.execute("ALTER TABLE places ALTER COLUMN closed_weekdays SET NOT NULL")
