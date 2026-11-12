# places, place_search 만 여기서 관리한다. Spring 쪽 테이블은 Flyway 가 맡는다.

from alembic import context
from sqlalchemy import create_engine

from app.config import settings


def url() -> str:
    # psycopg3 드라이버로 접속
    return settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_offline():
    context.configure(url=url(), literal_binds=True, version_table="alembic_version_ai")
    with context.begin_transaction():
        context.run_migrations()


def run_online():
    with create_engine(url()).connect() as conn:
        context.configure(connection=conn, version_table="alembic_version_ai")
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
