import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    try:
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as exc:
        logger.warning("Database initialization skipped: %s", exc)

