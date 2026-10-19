"""Small synthetic tables, independent of the original Olist download."""

import pandas as pd


def make_raw_data():
    """Four orders, five items, three buyers and a regional category tie."""
    return {
        "orders": pd.DataFrame(
            [
                ("o1", "c1", "2017-01-01 00:00:00", "delivered"),
                ("o2", "c2", "2017-02-15 12:00:00", "delivered"),
                ("o3", "c3", "2017-02-20 12:00:00", "delivered"),
                ("o4", "c4", "2017-02-28 12:00:00", "delivered"),
            ],
            columns=["order_id", "customer_id", "order_purchase_timestamp", "order_status"],
        ),
        "customers": pd.DataFrame(
            [
                ("c1", "u1", "city_a", "SP"),
                ("c2", "u1", "city_a", "SP"),
                ("c3", "u2", "city_b", "AM"),
                ("c4", "u3", "city_c", "AC"),
            ],
            columns=["customer_id", "customer_unique_id", "customer_city", "customer_state"],
        ),
        "order_items": pd.DataFrame(
            [
                ("o1", 1, "p1", "s1", 10.0, 2.0),
                ("o1", 2, "p2", "s1", 15.0, 3.0),
                ("o2", 1, "p1", "s1", 30.0, 4.0),
                ("o3", 1, "p1", "s2", 45.0, 5.0),
                ("o4", 1, "p2", "s2", 45.0, 6.0),
            ],
            columns=["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"],
        ),
        "products": pd.DataFrame(
            [("p1", "beleza"), ("p2", "livros")],
            columns=["product_id", "product_category_name"],
        ),
        "category_translation": pd.DataFrame(
            [("beleza", "health_beauty"), ("livros", "books")],
            columns=["product_category_name", "product_category_name_english"],
        ),
        "payments": pd.DataFrame(
            [("o1", 1, 20.0), ("o1", 2, 10.0), ("o2", 1, 34.0)],
            columns=["order_id", "payment_sequential", "payment_value"],
        ),
    }
