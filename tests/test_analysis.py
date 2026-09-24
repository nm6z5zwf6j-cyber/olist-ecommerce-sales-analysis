import unittest

import pandas as pd

from src.analysis import calculate_metrics


class CalculateMetricsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

