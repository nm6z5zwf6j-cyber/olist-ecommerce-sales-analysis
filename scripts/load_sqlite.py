"""Load the Olist CSV files into a local SQLite database."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd


TABLES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

SOURCE_KEYS = {
    "customers": ["customer_id"],
    "orders": ["order_id"],
    "order_items": ["order_id", "order_item_id"],
    "payments": ["order_id", "payment_sequential"],
    "products": ["product_id"],
    "category_translation": ["product_category_name"],
}


def load_database(raw_dir: Path, database_path: Path) -> None:
    """Validate source keys before replacing any existing SQLite tables."""
    missing = [filename for filename in TABLES.values() if not (raw_dir / filename).exists()]
    if missing:
        raise FileNotFoundError("Missing CSV files. Run scripts/download_data.py first.")

    # Check every source first: a late key conflict must leave the old DB intact.
    cleaned_tables = {}
    removed_counts = {}
    for table_name, filename in TABLES.items():
        frame = pd.read_csv(raw_dir / filename)
        cleaned = frame.drop_duplicates()
        key_columns = SOURCE_KEYS[table_name]
        keys = ", ".join(key_columns)
        missing_key = cleaned[key_columns].isna().any(axis=1)
        for column in key_columns:
            missing_key |= cleaned[column].astype("string").str.strip().eq("").fillna(False)
        if missing_key.any():
            raise ValueError(
                f"{table_name}: missing or blank key ({keys}) in "
                f"{int(missing_key.sum())} rows after removing exact duplicates. "
                "Fill source keys before loading SQLite."
            )
        conflicting = cleaned.duplicated(key_columns, keep=False)
        if conflicting.any():
            raise ValueError(
                f"{table_name}: conflicting key ({keys}) in "
                f"{int(conflicting.sum())} rows after removing exact duplicates. "
                "Resolve conflicting records before loading SQLite."
            )
        cleaned_tables[table_name] = cleaned
        removed_counts[table_name] = len(frame) - len(cleaned)

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_path)) as connection, connection:
        for table_name, cleaned in cleaned_tables.items():
            cleaned.to_sql(table_name, connection, if_exists="replace", index=False)
            removed = removed_counts[table_name]
            print(
                f"Loaded {table_name}: {len(cleaned):,} rows "
                f"({removed:,} exact duplicate rows removed)"
            )

        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id);
            CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
            CREATE INDEX IF NOT EXISTS idx_items_order_id ON order_items(order_id);
            CREATE INDEX IF NOT EXISTS idx_items_product_id ON order_items(product_id);
            CREATE INDEX IF NOT EXISTS idx_customers_customer_id ON customers(customer_id);
            CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id);
            CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
            """
        )
    print(f"SQLite database created: {database_path}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    load_database(root / "data" / "raw", root / "data" / "olist.db")

