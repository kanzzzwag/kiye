import os

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

if settings.database_url.startswith("sqlite"):
    os.makedirs("./data", exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

MIGRATIONS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


class Base(DeclarativeBase):
    pass


def init_db():
    """Bring the schema to the latest Alembic revision. A database created by the first skeleton
    (tables exist, no alembic_version) is stamped as 0001 first, so its data is kept."""
    from alembic import command
    from alembic.config import Config

    from . import models  # noqa: F401

    cfg = Config()
    cfg.set_main_option("script_location", MIGRATIONS)
    tables = set(inspect(engine).get_table_names())
    if "jobs" in tables and "alembic_version" not in tables:
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")
