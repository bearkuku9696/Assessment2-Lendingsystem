from collections.abc import Generator
from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from equipment_lending.config import PROJECT_ROOT, settings


class Base(DeclarativeBase):
    """Shared base for future user, equipment, and booking models."""


engine = create_engine(
    URL.create("sqlite", database=str(PROJECT_ROOT / settings.database_path)),
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def immediate_transaction(session: Session):
    """Reserve SQLite's writer before reading data used to decide an update.

    A deferred transaction alone cannot serialize competing approval checks.
    This lock also works across separate server processes, not just threads.
    """
    with session.begin():
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield


def get_session() -> Generator[Session, None, None]:
    # Each request owns its session. Services explicitly commit write transactions.
    with SessionLocal() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_session)]
