"""Load the Olist CSV files into a local SQLite database."""

from __future__ import annotations

import sqlite3
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


def load_database(raw_dir: Path, database_path: Path) -> None:
    missing = [filename for filename in TABLES.values() if not (raw_dir / filename).exists()]
    if missing:
        raise FileNotFoundError("Missing CSV files. Run scripts/download_data.py first.")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        for table_name, filename in TABLES.items():
            frame = pd.read_csv(raw_dir / filename)
            frame.to_sql(table_name, connection, if_exists="replace", index=False)
            print(f"Loaded {table_name}: {len(frame):,} rows")

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

