"""Transactional payment outbox and restart-safe, per-workspace ECD lifecycle."""
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DesktopActivation(Base):
    __tablename__ = "desktop_activations"

    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    step: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(nullable=True)
    # ECD CreateDesktops/RenewDesktops have no ClientToken. An ambiguous
    # purchase must be reconciled, never blindly submitted a second time.
    purchase_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    purchase_started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    purchase_baseline: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (Index("ix_desktop_activations_due", "next_run_at", "lease_until"),)
