import sqlite3
import unittest
from pathlib import Path

import pandas as pd

from src.analysis import build_summary_tables, calculate_metrics, prepare_sales
from tests.fixtures import make_raw_data


class SqlParityTests(unittest.TestCase):
    def setUp(self):
        self.raw = make_raw_data()
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.load_tables()
        sql_path = Path(__file__).resolve().parents[1] / "sql" / "analysis.sql"
        self.queries = ["-- QUERY " + part for part in sql_path.read_text(encoding="utf-8").split("-- QUERY ")[1:]]
        self.sales, _ = prepare_sales(self.raw)
        self.metrics = calculate_metrics(self.sales)
        self.tables = build_summary_tables(self.sales)

    def load_tables(self):
        for name, frame in self.raw.items():
            frame.to_sql(name, self.connection, index=False, if_exists="replace")

    def query(self, number):
        return pd.read_sql_query(self.queries[number - 1], self.connection)

    def assert_rows_equal(self, actual, expected, columns, sort_by):
        pd.testing.assert_frame_equal(
            actual[columns].sort_values(sort_by).reset_index(drop=True),
            expected[columns].sort_values(sort_by).reset_index(drop=True),
            check_dtype=False,
            atol=0.005,
            rtol=0,
        )

    def test_all_eight_queries_execute(self):
        self.assertEqual(len(self.queries), 8)
        for number in range(1, 9):
            with self.subTest(query=number):
                self.assertFalse(self.query(number).empty)

    def test_headline_metrics_match_python(self):
        result = self.query(1).iloc[0]
        for key in ("total_revenue_brl", "orders", "average_order_value_brl"):
            with self.subTest(metric=key):
                self.assertEqual(result[key], self.metrics[key])

    def test_monthly_metrics_match_python(self):
        self.assert_rows_equal(
            self.query(2), self.tables["monthly_sales"].round(2),
            ["purchase_month", "revenue_brl", "orders", "average_order_value_brl"],
            ["purchase_month"],
        )

    def test_category_metrics_match_python(self):
        self.assert_rows_equal(
            self.query(3), self.tables["category_sales"],
            ["product_category", "revenue_brl", "orders", "items"], ["product_category"],
        )

    def test_region_metrics_match_python(self):
        self.assert_rows_equal(
            self.query(4), self.tables["region_sales"],
            ["customer_region", "revenue_brl", "orders"], ["customer_region"],
        )

    def test_product_metrics_match_python(self):
        self.assert_rows_equal(
            self.query(5), self.tables["top_products"],
            ["product_id", "product_category", "items_sold", "orders", "revenue_brl"], ["product_id"],
        )

    def test_repeat_customer_metrics_match_python(self):
        result = self.query(6).iloc[0]
        for key in ("unique_customers", "repeat_customers", "repeat_customer_rate_pct"):
            with self.subTest(metric=key):
                self.assertEqual(result[key], self.metrics[key])

    def test_growth_uses_previous_month_and_first_month_is_undefined(self):
        result = self.query(7)
        self.assertEqual(result["purchase_month"].tolist(), ["2017-01", "2017-02"])
        self.assertEqual(result["revenue_brl"].tolist(), [25.0, 120.0])
        self.assertTrue(pd.isna(result.iloc[0]["month_over_month_growth_pct"]))
        self.assertEqual(result.iloc[1]["month_over_month_growth_pct"], 380.0)

    def test_category_ranking_preserves_ties(self):
        expected = pd.DataFrame(
            [("North", "books", 45.0), ("North", "health_beauty", 45.0), ("Southeast", "health_beauty", 40.0)],
            columns=["customer_region", "product_category", "revenue_brl"],
        )
        self.assert_rows_equal(
            self.query(8), expected, list(expected.columns), ["customer_region", "product_category"],
        )

    def test_empty_selection_matches_python_null_semantics(self):
        self.raw["orders"]["order_status"] = "canceled"
        self.load_tables()
        sales, _ = prepare_sales(self.raw)
        metrics = calculate_metrics(sales)
        headline = self.query(1).iloc[0]
        repeat = self.query(6).iloc[0]
        self.assertEqual(headline["orders"], metrics["orders"])
        self.assertEqual(headline["total_revenue_brl"], metrics["total_revenue_brl"])
        self.assertIsNone(headline["average_order_value_brl"])
        self.assertEqual(repeat["unique_customers"], metrics["unique_customers"])
        self.assertEqual(repeat["repeat_customers"], metrics["repeat_customers"])
        self.assertIsNone(repeat["repeat_customer_rate_pct"])


if __name__ == "__main__":
    unittest.main()
