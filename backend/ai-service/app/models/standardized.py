"""The record of one existence check against the vector embedding DB.

`POST /standardized/check` writes one row; `POST /standardized/add` reads it
back by id and inserts exactly the rows the check judged NEW.

Why a table and not a client-supplied list. Add takes a `batch_id`, so the
rows that get indexed are the rows *this service* decided were new - not
whatever a caller chooses to send back. Round-tripping the decision through
the client would make the check advisory, and the one guarantee the pair
exists to provide is that a row already in the index cannot be added again.

It is also the audit trail: which payload was offered, how many rows were
already present, and which of them were eventually written.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class StandardizationBatch(Base):
    """One batch of standard-format rows offered by pipeline-one."""

    __tablename__ = "standardization_batch"
    __table_args__ = (Index("ix_standardization_batch_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    status: Mapped[str] = mapped_column(String(16), default="CHECKED", index=True)
    """CHECKED -> the split is known. ADDED -> the new rows were indexed.

    A batch is added at most once: a second add against the same id is refused
    rather than reindexing rows that are now, by definition, already present."""

    source: Mapped[str | None] = mapped_column(String(64))
    """Which pipeline produced these rows, as the payload declared itself -
    'pipeline-one' for a forwarded session. A label, never trusted."""

    source_session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    """pipeline-one's own review session id, when the forwarder envelope
    carried one. This is the join between a reviewed extraction over there and
    an indexed material over here."""

    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    new_rows: Mapped[int] = mapped_column(Integer, default=0)
    existing_rows: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    added_rows: Mapped[int] = mapped_column(Integer, default=0)

    payload_json: Mapped[str] = mapped_column(Text)
    """The verdict for every row, plus the standard-format row itself for the
    ones judged NEW. Only those carry their data forward - a row that already
    exists needs no second copy of its fields to be stored."""

    requested_by: Mapped[str | None] = mapped_column(String(120))
    cpse_code: Mapped[str | None] = mapped_column(String(16), index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
