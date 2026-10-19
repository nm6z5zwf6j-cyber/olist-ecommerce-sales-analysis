import unittest

import pandas as pd

from src.analysis import build_summary_tables, calculate_metrics, prepare_sales
from tests.fixtures import make_raw_data


class PrepareSalesTests(unittest.TestCase):
    def setUp(self):
        self.raw = make_raw_data()

    def test_end_to_end_metrics_exclude_freight_and_split_payments(self):
        sales, _ = prepare_sales(self.raw)
        self.assertEqual(
            calculate_metrics(sales),
            {
                "total_revenue_brl": 145.0, "orders": 4, "items": 5,
                "average_order_value_brl": 36.25, "unique_customers": 3,
                "repeat_customers": 1, "repeat_customer_rate_pct": 33.33,
            },
        )

    def test_window_includes_start_and_excludes_end(self):
        self.raw["orders"]["order_purchase_timestamp"] = [
            "2017-01-01 00:00:00", "2018-08-31 23:59:59",
            "2018-09-01 00:00:00", "2016-12-31 23:59:59",
        ]
        sales, stats = prepare_sales(self.raw)
        self.assertEqual(set(sales["order_id"]), {"o1", "o2"})
        self.assertEqual(stats["delivered_orders_outside_analysis_window"], 2)

    def test_invalid_dates_and_non_delivered_orders_are_excluded(self):
        self.raw["orders"].loc[0, "order_status"] = "canceled"
        self.raw["orders"].loc[1, "order_purchase_timestamp"] = "bad-date"
        self.raw["orders"].loc[2, "order_purchase_timestamp"] = None
        sales, stats = prepare_sales(self.raw)
        self.assertEqual(sales["order_id"].tolist(), ["o4"])
        self.assertEqual(stats["non_delivered_orders_excluded"], 1)
        self.assertEqual(stats["delivered_orders_outside_analysis_window"], 2)

    def test_negative_or_missing_money_is_excluded_and_zero_is_retained(self):
        self.raw["order_items"].loc[0, "price"] = -1.0
        self.raw["order_items"].loc[1, "freight_value"] = -1.0
        self.raw["order_items"].loc[2, "price"] = float("nan")
        self.raw["order_items"].loc[3, "freight_value"] = float("nan")
        self.raw["order_items"].loc[4, ["price", "freight_value"]] = 0.0
        sales, stats = prepare_sales(self.raw)
        self.assertEqual(sales["order_id"].tolist(), ["o4"])
        self.assertEqual(stats["invalid_price_or_freight_rows"], 4)
        self.assertEqual(calculate_metrics(sales)["total_revenue_brl"], 0.0)

    def test_missing_product_and_translation_preserve_revenue(self):
        self.raw["products"] = self.raw["products"].iloc[:1]
        self.raw["category_translation"] = self.raw["category_translation"].iloc[:0]
        sales, stats = prepare_sales(self.raw)
        self.assertTrue(sales["product_category"].eq("unknown").all())
        self.assertEqual(stats["missing_category_item_rows"], 5)
        self.assertEqual(calculate_metrics(sales)["total_revenue_brl"], 145.0)

    def test_unknown_state_is_labeled_without_dropping_sales(self):
        self.raw["customers"].loc[2, "customer_state"] = "XX"
        sales, stats = prepare_sales(self.raw)
        self.assertEqual(sales.loc[sales["order_id"].eq("o3"), "customer_region"].item(), "Unknown")
        self.assertEqual(stats["unknown_region_item_rows"], 1)
        self.assertEqual(len(sales), 5)

    def test_exact_source_duplicates_do_not_inflate_revenue(self):
        for name, frame in list(self.raw.items()):
            self.raw[name] = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
        sales, stats = prepare_sales(self.raw)
        self.assertEqual(stats["raw_exact_duplicates"], 6)
        self.assertEqual(calculate_metrics(sales)["total_revenue_brl"], 145.0)

    def test_conflicting_customer_key_fails_before_revenue_inflation(self):
        extra = self.raw["customers"].iloc[:1].copy()
        extra["customer_state"] = "RJ"
        self.raw["customers"] = pd.concat([self.raw["customers"], extra], ignore_index=True)
        with self.assertRaises(pd.errors.MergeError):
            prepare_sales(self.raw)

    def test_conflicting_item_key_fails_before_revenue_inflation(self):
        extra = self.raw["order_items"].iloc[:1].copy()
        extra["price"] = 999.0
        self.raw["order_items"] = pd.concat([self.raw["order_items"], extra], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate order-item keys"):
            prepare_sales(self.raw)

    def test_no_eligible_orders_produces_empty_sales_and_defined_counts(self):
        self.raw["orders"]["order_status"] = "canceled"
        sales, stats = prepare_sales(self.raw)
        self.assertTrue(sales.empty)
        self.assertEqual(calculate_metrics(sales)["orders"], 0)
        self.assertEqual(stats["non_delivered_orders_excluded"], 4)

    def test_input_tables_are_not_modified(self):
        originals = {name: frame.copy(deep=True) for name, frame in self.raw.items()}
        prepare_sales(self.raw)
        for name, frame in self.raw.items():
            with self.subTest(table=name):
                pd.testing.assert_frame_equal(frame, originals[name])

    def test_summary_revenue_reconciles_and_category_orders_are_not_additive(self):
        sales, _ = prepare_sales(self.raw)
        tables = build_summary_tables(sales)
        for name in ("monthly_sales", "category_sales", "region_sales", "top_products"):
            with self.subTest(table=name):
                self.assertEqual(tables[name]["revenue_brl"].sum(), 145.0)
        self.assertEqual(tables["monthly_sales"]["orders"].sum(), 4)
        self.assertEqual(tables["category_sales"]["orders"].sum(), 5)


if __name__ == "__main__":
    unittest.main()
