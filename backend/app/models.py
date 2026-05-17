from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def uuid_str() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="planner")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryUpload(Base):
    __tablename__ = "inventory_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    filename: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_type: Mapped[str] = mapped_column(String(64), index=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    efficiency_score: Mapped[float] = mapped_column(Float, default=0)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(255))
    format: Mapped[str] = mapped_column(String(16), default="json")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

