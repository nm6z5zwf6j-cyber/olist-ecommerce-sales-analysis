"""Execute every labeled query in sql/analysis.sql against SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def run_queries(sql_path: Path, database_path: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8")
    queries = ["-- QUERY " + part for part in sql_text.split("-- QUERY ")[1:]]
    if not queries:
        raise ValueError("No labeled queries found in the SQL file.")

    with sqlite3.connect(database_path) as connection:
        for number, query in enumerate(queries, start=1):
            title = query.splitlines()[0].removeprefix("-- ")
            result = pd.read_sql_query(query, connection)
            print(f"\n{title}")
            print(result.to_string(index=False))


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    run_queries(root / "sql" / "analysis.sql", root / "data" / "olist.db")

