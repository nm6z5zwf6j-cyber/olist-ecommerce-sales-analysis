import unittest

import pandas as pd

from src.analysis import build_cohort_retention, calculate_metrics, prepare_sales
from tests.fixtures import make_raw_data


class CalculateMetricsTests(unittest.TestCase):
    def test_empty_input_has_zero_counts_and_undefined_rates(self):
        sales = pd.DataFrame(
            columns=["order_id", "order_item_id", "customer_unique_id", "item_revenue"]
        )
        self.assertEqual(
            calculate_metrics(sales),
            {
                "orders": 0,
                "items": 0,
                "total_revenue_brl": 0.0,
                "average_order_value_brl": None,
                "unique_customers": 0,
                "repeat_customers": 0,
                "repeat_customer_rate_pct": None,
            },
        )

    def test_zero_revenue_is_a_valid_observation(self):
        sales = pd.DataFrame(
            {"order_id": ["o1"], "customer_unique_id": ["c1"], "item_revenue": [0.0]}
        )
        metrics = calculate_metrics(sales)
        self.assertEqual(metrics["orders"], 1)
        self.assertEqual(metrics["average_order_value_brl"], 0.0)
        self.assertEqual(metrics["repeat_customer_rate_pct"], 0.0)

    def test_multi_item_order_is_counted_once(self):
        sales = pd.DataFrame(
            {
                "order_id": ["o1", "o1", "o2", "o3"],
                "order_item_id": [1, 2, 1, 1],
                "customer_unique_id": ["c1", "c1", "c1", "c2"],
                "item_revenue": [10.0, 15.0, 30.0, 45.0],
            }
        )

        metrics = calculate_metrics(sales)

        self.assertEqual(metrics["orders"], 3)
        self.assertEqual(metrics["items"], 4)
        self.assertEqual(metrics["total_revenue_brl"], 100.0)
        self.assertEqual(metrics["average_order_value_brl"], 33.33)
        self.assertEqual(metrics["unique_customers"], 2)
        self.assertEqual(metrics["repeat_customers"], 1)
        self.assertEqual(metrics["repeat_customer_rate_pct"], 50.0)


class CohortRetentionTests(unittest.TestCase):
    def test_only_complete_six_month_cohorts_are_reported(self):
        sales, _ = prepare_sales(make_raw_data())
        cohorts = build_cohort_retention(sales)
        self.assertEqual(cohorts["cohort_month"].unique().tolist(), ["2017-01", "2017-02"])
        self.assertEqual(len(cohorts), 12)
        january = cohorts[cohorts["cohort_month"].eq("2017-01")]
        self.assertEqual(january["cohort_size"].unique().tolist(), [1])
        self.assertEqual(january["retention_pct"].tolist(), [100.0, 100.0, 0.0, 0.0, 0.0, 0.0])
        february = cohorts[cohorts["cohort_month"].eq("2017-02")]
        self.assertEqual(february["cohort_size"].unique().tolist(), [2])
        self.assertEqual(february["retention_pct"].tolist(), [100.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    def test_empty_sales_returns_a_well_shaped_table(self):
        columns = ["cohort_month", "months_since_first_order", "customers", "cohort_size", "retention_pct"]
        self.assertEqual(list(build_cohort_retention(pd.DataFrame()).columns), columns)


if __name__ == "__main__":
    unittest.main()

