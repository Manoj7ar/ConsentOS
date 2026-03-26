from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def build_session_factory(database_url: str):
    engine = build_engine(database_url)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False), engine


def init_db(engine) -> None:
    from app.models import activity_log, connected_account, permission, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_connected_account_columns(engine)


def session_scope(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_connected_account_columns(engine) -> None:
    inspector = inspect(engine)
    if "connected_accounts" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("connected_accounts")}
    required_columns = {
        "last_synced_at": "TIMESTAMP NULL",
        "auth0_created_at": "TIMESTAMP NULL",
        "auth0_expires_at": "TIMESTAMP NULL",
        "status_detail": "VARCHAR(255) NULL",
    }

    missing = {name: definition for name, definition in required_columns.items() if name not in existing}
    if not missing:
        return

    with engine.begin() as connection:
        for name, definition in missing.items():
            connection.execute(text(f"ALTER TABLE connected_accounts ADD COLUMN {name} {definition}"))
