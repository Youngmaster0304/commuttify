"""SQLAlchemy engine/session helpers (psycopg2 driver)."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from . import config


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        config.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def ping() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def run_sql_file(path: str) -> None:
    """Execute a .sql script (statements split on ';' at top level)."""
    sql = open(path, encoding="utf-8").read()
    with get_engine().begin() as conn:
        for stmt in _split_sql(sql):
            if stmt.strip():
                conn.execute(text(stmt))


def _split_sql(sql: str) -> list[str]:
    """Split SQL on top-level semicolons; ignore those inside $$ blocks,
    'string literals', and -- line comments."""
    parts: list[str] = []
    buf: list[str] = []
    in_dollar = False
    in_single = False
    in_comment = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < len(sql) else ""
        if in_comment:
            buf.append(ch)
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if not in_dollar and not in_single and ch == "-" and nxt == "-":
            in_comment = True
            buf.append(ch)
            buf.append(nxt)
            i += 2
            continue
        if not in_dollar and not in_single and ch == "$" and nxt == "$":
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        if not in_dollar and ch == "'":
            if in_single and nxt == "'":
                buf.append("''")
                i += 2
                continue
            in_single = not in_single
        if ch == ";" and not in_dollar and not in_single:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts
