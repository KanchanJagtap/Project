"""
SQLAlchemy 2.0 Declarative Base and Type Helpers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import ARRAY, Float, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# Compatible column types across PostgreSQL (production) and SQLite (tests)
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
ARRAY_STR_TYPE = ARRAY(String).with_variant(JSON(), "sqlite")
ARRAY_FLOAT_TYPE = ARRAY(Float).with_variant(JSON(), "sqlite")
UUID_TYPE = Uuid(as_uuid=True)


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy 2.0 models."""
    pass
