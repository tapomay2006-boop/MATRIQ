"""One source of "now" for anything that gets written to the database.

Every timestamp column in this schema is `TIMESTAMP WITHOUT TIME ZONE` - the
convention `created_at`, `occurred_at`, `mapped_at` and the rest have always
followed, because they are all filled by `server_default=func.now()`.

Python code that wrote `datetime.now(UTC)` into one of those columns therefore
handed asyncpg an offset-aware value for a naive column, and asyncpg refuses to
encode that:

    asyncpg.exceptions.DataError: invalid input for query argument $3
    (can't subtract offset-naive and offset-aware datetimes)

SQLite does not care, so the whole test suite passed while `POST
/standardized/add` was broken against Postgres and three other call sites were
quietly logging the failure as a warning. That is precisely the class of defect
tests/test_postgres_types.py now exists to catch.

`utcnow()` returns the current UTC instant with the offset stripped: the same
moment the aware value described, in the form every column in this schema
stores. It is a wall-clock UTC timestamp, so comparisons and durations across
rows stay correct; what it is not is a value that can be compared against an
aware datetime without attaching UTC first.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """The current UTC instant, naive - ready to store in this schema."""
    return datetime.now(UTC).replace(tzinfo=None)
