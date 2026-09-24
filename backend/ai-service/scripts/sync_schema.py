"""Add columns the models declare but the database does not have.

`app/main.py` builds the schema with `Base.metadata.create_all`, which CREATEs
missing tables and does nothing at all to tables that already exist. So every
column added to a model since a database was first created is invisible to it,
and the mismatch only surfaces at runtime as:

    asyncpg.exceptions.UndefinedColumnError: column material.updated_at does not exist

This script closes that gap. It is deliberately **additive only**:

  * it ADDs columns that models declare and the database lacks
  * it never drops a column, never drops a table, never changes a type
  * a table the database has and the models do not is reported and left alone

so running it cannot lose data. It is idempotent - a second run finds nothing
to do - and it prints its plan and exits unless you pass `--apply`.

    python scripts/sync_schema.py            # show the plan
    python scripts/sync_schema.py --apply    # run it

A NOT NULL column needs a value for the rows that already exist. The model's own
default is used where it has one; otherwise a type-appropriate empty value is
chosen and printed, so you can see exactly what existing rows will be given
before anything runs.

This is a stopgap, not a migration system. A project that keeps changing its
schema wants Alembic, which records *which* migrations have run rather than
inferring the difference each time. What this buys is a working database today
without hand-writing thirty ALTER statements.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.schema import CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, engine  # noqa: E402
from app.models import *  # noqa: F401,F403,E402  - register every mapper

#: Values given to existing rows when a NOT NULL column is added and the model
#: declares no default of its own. Keyed by the SQL type name.
_FALLBACK = {
    "VARCHAR": "''",
    "TEXT": "''",
    "INTEGER": "0",
    "FLOAT": "0",
    "BOOLEAN": "false",
    "DATETIME": "now()",
    "TIMESTAMP": "now()",
}


def _default_sql(column) -> str | None:
    """What existing rows should get for this column, as a SQL literal."""
    if column.server_default is not None:
        arg = str(column.server_default.arg)
        if (
            not (arg.startswith("'") and arg.endswith("'"))
            and arg.lower() not in ("now()", "current_timestamp", "true", "false", "null")
            and not arg.replace(".", "", 1).isdigit()
        ):
            return "'" + arg.replace("'", "''") + "'"
        return arg
    if column.default is not None and not column.default.is_callable:
        value = column.default.arg
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
    if column.nullable:
        return None
    # NOT NULL with nothing to fall back on: pick by type and say so.
    name = type(column.type).__name__.upper()
    for key, literal in _FALLBACK.items():
        if key in name:
            return literal
    return "''"


async def plan() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """Returns (statements, missing_tables, extra_tables)."""
    async with engine.connect() as connection:
        rows = (await connection.execute(text("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
        """))).all()

    live: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        live.setdefault(table_name, set()).add(column_name)

    statements: list[tuple[str, str]] = []
    missing_tables: list[str] = []

    for table in Base.metadata.sorted_tables:
        if table.name not in live:
            # create_all will handle this one; report it so the run is complete.
            missing_tables.append(table.name)
            continue

        for column in table.columns:
            if column.name in live[table.name]:
                continue

            column_type = column.type.compile(engine.dialect)
            sql = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'
            default = _default_sql(column)
            if default is not None:
                sql += f" DEFAULT {default}"
            if not column.nullable:
                sql += " NOT NULL"
            statements.append((f"{table.name}.{column.name}", sql))

    extra = sorted(set(live) - {t.name for t in Base.metadata.sorted_tables})
    return statements, missing_tables, extra


async def main(apply: bool) -> int:
    statements, missing_tables, extra = await plan()

    if extra:
        print("Tables in the database with no model. LEFT ALONE - this script")
        print("never drops anything; remove them by hand if they are truly dead:")
        for name in extra:
            print(f"  - {name}")
        print()

    if missing_tables:
        print("Tables the models declare that do not exist yet.")
        print("These are created by create_all at startup, and by --apply here:")
        for name in missing_tables:
            print(f"  + {name}")
        print()

    if not statements and not missing_tables:
        print("Schema is already in sync. Nothing to do.")
        await engine.dispose()
        return 0

    if statements:
        print(f"{len(statements)} column(s) to add:\n")
        for label, sql in statements:
            print(f"  {label:44s} {sql.split('ADD COLUMN', 1)[1].strip()}")
        print()

    if not apply:
        print("Dry run. Nothing was changed. Re-run with --apply to execute.")
        await engine.dispose()
        return 0

    async with engine.begin() as connection:
        if missing_tables:
            for table in Base.metadata.sorted_tables:
                if table.name in missing_tables:
                    await connection.execute(CreateTable(table))
                    print(f"  created  {table.name}")
        for label, sql in statements:
            await connection.execute(text(sql))
            print(f"  added    {label}")

    # One transaction: either the schema moves forward or nothing does.
    print(f"\nDone. {len(statements)} column(s) added, "
          f"{len(missing_tables)} table(s) created.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="execute the plan (without this the script only prints it)",
    )
    raise SystemExit(asyncio.run(main(parser.parse_args().apply)))
