from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.user import utcnow


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    external_user_id: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth0_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auth0_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="connected_accounts")
