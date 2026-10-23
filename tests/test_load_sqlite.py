import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from scripts.load_sqlite import TABLES, load_database
from src.analysis import calculate_metrics, prepare_sales
from tests.fixtures import make_raw_data


class LoadDatabaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.raw_dir = Path(temporary.name) / "raw"
        self.raw_dir.mkdir()
        self.database_path = Path(temporary.name) / "olist.db"
        sql_path = Path(__file__).resolve().parents[1] / "sql" / "analysis.sql"
        self.queries = [
            "-- QUERY " + part
            for part in sql_path.read_text(encoding="utf-8").split("-- QUERY ")[1:]
        ]

    def load_csv_tables(self, raw):
        for name, filename in TABLES.items():
            raw[name].to_csv(self.raw_dir / filename, index=False)
        with contextlib.redirect_stdout(io.StringIO()):
            load_database(self.raw_dir, self.database_path)

    def test_exact_duplicates_in_each_source_do_not_change_any_query(self):
        clean_raw = make_raw_data()
        duplicated_raw = {
            name: pd.concat([frame, frame.iloc[:1]], ignore_index=True)
            for name, frame in clean_raw.items()
        }
        self.load_csv_tables(duplicated_raw)

        with (
            contextlib.closing(sqlite3.connect(self.database_path)) as actual_db,
            contextlib.closing(sqlite3.connect(":memory:")) as expected_db,
        ):
            for name, frame in clean_raw.items():
                frame.to_sql(name, expected_db, index=False)
                with self.subTest(table=name):
                    count = actual_db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                    self.assertEqual(count, len(frame))

            for number, query in enumerate(self.queries, start=1):
                with self.subTest(query=number):
                    pd.testing.assert_frame_equal(
                        pd.read_sql_query(query, actual_db),
                        pd.read_sql_query(query, expected_db),
                    )

            sales, _ = prepare_sales(duplicated_raw)
            metrics = calculate_metrics(sales)
            headline = pd.read_sql_query(self.queries[0], actual_db).iloc[0]
            self.assertEqual(headline["total_revenue_brl"], 145.0)
            self.assertEqual(headline["total_revenue_brl"], metrics["total_revenue_brl"])
            self.assertEqual(headline["orders"], metrics["orders"])

    def test_distinct_items_and_payment_parts_are_not_collapsed(self):
        raw = make_raw_data()
        extra_item = raw["order_items"].iloc[:1].copy()
        extra_item["order_item_id"] = 3
        raw["order_items"] = pd.concat(
            [raw["order_items"], extra_item, extra_item], ignore_index=True,
        )
        extra_payment = raw["payments"].iloc[:1].copy()
        extra_payment["payment_sequential"] = 3
        raw["payments"] = pd.concat(
            [raw["payments"], extra_payment, extra_payment], ignore_index=True,
        )
        self.load_csv_tables(raw)

        with contextlib.closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM order_items").fetchone()[0], 6)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0], 4)
            headline = pd.read_sql_query(self.queries[0], connection).iloc[0]
            self.assertEqual(headline["orders"], 4)
            self.assertEqual(headline["total_revenue_brl"], 155.0)
            sales, _ = prepare_sales(raw)
            self.assertEqual(headline["total_revenue_brl"], calculate_metrics(sales)["total_revenue_brl"])

    def assert_queries_match_reference(self, raw, reference):
        self.load_csv_tables(raw)
        sales, _ = prepare_sales(raw)
        metrics = calculate_metrics(sales)
        with (
            contextlib.closing(sqlite3.connect(self.database_path)) as actual_db,
            contextlib.closing(sqlite3.connect(":memory:")) as expected_db,
        ):
            for name, frame in reference.items():
                frame.to_sql(name, expected_db, index=False)
            for number, query in enumerate(self.queries, start=1):
                with self.subTest(query=number):
                    pd.testing.assert_frame_equal(
                        pd.read_sql_query(query, actual_db),
                        pd.read_sql_query(query, expected_db),
                    )
            for number in (1, 6):
                result = pd.read_sql_query(self.queries[number - 1], actual_db).iloc[0]
                for name, value in result.items():
                    with self.subTest(query=number, metric=name):
                        self.assertEqual(value, metrics[name])

    def test_missing_customer_row_excludes_its_order_from_every_query(self):
        raw = make_raw_data()
        raw["customers"] = raw["customers"][raw["customers"]["customer_id"].ne("c1")]
        reference = {name: frame.copy() for name, frame in raw.items()}
        reference["orders"] = reference["orders"][reference["orders"]["order_id"].ne("o1")]
        reference["order_items"] = reference["order_items"][reference["order_items"]["order_id"].ne("o1")]
        sales, _ = prepare_sales(raw)
        self.assertEqual(calculate_metrics(sales)["total_revenue_brl"], 120.0)
        self.assertEqual(calculate_metrics(sales)["orders"], 3)
        self.assert_queries_match_reference(raw, reference)

    def test_no_customer_rows_produces_empty_selection_in_every_query(self):
        raw = make_raw_data()
        raw["customers"] = raw["customers"].iloc[:0]
        reference = {name: frame.copy() for name, frame in raw.items()}
        reference["orders"] = reference["orders"].iloc[:0]
        reference["order_items"] = reference["order_items"].iloc[:0]
        self.assert_queries_match_reference(raw, reference)

    def test_conflicting_keys_are_rejected_before_creating_any_database(self):
        changed_fields = {
            "customers": ("customer_state", "RJ"),
            "orders": ("order_status", "canceled"),
            "order_items": ("price", 999.0),
            "payments": ("payment_value", 999.0),
            "products": ("product_category_name", "other"),
            "category_translation": ("product_category_name_english", "other"),
        }
        for name, (column, value) in changed_fields.items():
            with self.subTest(table=name):
                raw = make_raw_data()
                extra = raw[name].iloc[:1].copy()
                extra[column] = value
                raw[name] = pd.concat([raw[name], extra], ignore_index=True)
                self.database_path = self.raw_dir.parent / f"{name}.db"
                with self.assertRaisesRegex(ValueError, f"{name}: conflicting key"):
                    self.load_csv_tables(raw)
                self.assertFalse(self.database_path.exists())

    def test_late_key_conflict_preserves_existing_database(self):
        self.load_csv_tables(make_raw_data())
        before = self.database_path.read_bytes()
        changed = make_raw_data()
        changed["orders"]["order_status"] = "canceled"
        extra = changed["category_translation"].iloc[:1].copy()
        extra["product_category_name_english"] = "other"
        changed["category_translation"] = pd.concat(
            [changed["category_translation"], extra], ignore_index=True,
        )
        with self.assertRaisesRegex(ValueError, "category_translation: conflicting key"):
            self.load_csv_tables(changed)
        self.assertEqual(self.database_path.read_bytes(), before)
        with contextlib.closing(sqlite3.connect(self.database_path)) as connection:
            headline = pd.read_sql_query(self.queries[0], connection).iloc[0]
            self.assertEqual(headline["total_revenue_brl"], 145.0)
            self.assertEqual(headline["orders"], 4)


if __name__ == "__main__":
    unittest.main()
