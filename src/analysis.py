"""Reproducible sales analysis for the Olist e-commerce dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


ANALYSIS_START = pd.Timestamp("2017-01-01")
ANALYSIS_END_EXCLUSIVE = pd.Timestamp("2018-09-01")

REQUIRED_FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "payments": "olist_order_payments_dataset.csv",
}

STATE_TO_REGION = {
    "AC": "North",
    "AP": "North",
    "AM": "North",
    "PA": "North",
    "RO": "North",
    "RR": "North",
    "TO": "North",
    "AL": "Northeast",
    "BA": "Northeast",
    "CE": "Northeast",
    "MA": "Northeast",
    "PB": "Northeast",
    "PE": "Northeast",
    "PI": "Northeast",
    "RN": "Northeast",
    "SE": "Northeast",
    "DF": "Central-West",
    "GO": "Central-West",
    "MT": "Central-West",
    "MS": "Central-West",
    "ES": "Southeast",
    "MG": "Southeast",
    "RJ": "Southeast",
    "SP": "Southeast",
    "PR": "South",
    "RS": "South",
    "SC": "South",
}


def load_raw_data(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Load the six source tables used by the project."""
    missing = [filename for filename in REQUIRED_FILES.values() if not (raw_dir / filename).exists()]
    if missing:
        joined = "\n- ".join(missing)
        raise FileNotFoundError(
            "Missing source files. Run `python scripts/download_data.py` first:\n- " + joined
        )

    return {
        name: pd.read_csv(raw_dir / filename)
        for name, filename in REQUIRED_FILES.items()
    }


def prepare_sales(
    raw: Mapping[str, pd.DataFrame],
    start: pd.Timestamp = ANALYSIS_START,
    end_exclusive: pd.Timestamp = ANALYSIS_END_EXCLUSIVE,
) -> tuple[pd.DataFrame, dict[str, int | float]]:
    """Clean and join the source tables at order-item grain."""
    tables = {name: frame.drop_duplicates().copy() for name, frame in raw.items()}

    orders = tables["orders"]
    orders["order_purchase_timestamp"] = pd.to_datetime(
        orders["order_purchase_timestamp"], errors="coerce"
    )

    items = tables["order_items"]
    valid_items = items[items["price"].ge(0) & items["freight_value"].ge(0)].copy()

    eligible_orders = orders[
        orders["order_status"].eq("delivered")
        & orders["order_purchase_timestamp"].notna()
        & orders["order_purchase_timestamp"].ge(start)
        & orders["order_purchase_timestamp"].lt(end_exclusive)
    ].copy()

    customers = tables["customers"][
        ["customer_id", "customer_unique_id", "customer_city", "customer_state"]
    ].copy()

    products = tables["products"][["product_id", "product_category_name"]].copy()
    category_translation = tables["category_translation"].copy()
    products = products.merge(
        category_translation,
        on="product_category_name",
        how="left",
        validate="many_to_one",
    )
    products["product_category"] = products["product_category_name_english"].fillna(
        "unknown"
    )

    sales = (
        eligible_orders[
            ["order_id", "customer_id", "order_purchase_timestamp", "order_status"]
        ]
        .merge(customers, on="customer_id", how="inner", validate="many_to_one")
        .merge(valid_items, on="order_id", how="inner", validate="one_to_many")
        .merge(
            products[["product_id", "product_category"]],
            on="product_id",
            how="left",
            validate="many_to_one",
        )
    )

    sales["product_category"] = sales["product_category"].fillna("unknown")
    sales["customer_region"] = sales["customer_state"].map(STATE_TO_REGION).fillna(
        "Unknown"
    )
    sales["purchase_month"] = sales["order_purchase_timestamp"].dt.to_period("M").astype(str)
    sales["item_revenue"] = sales["price"].astype(float)

    output_columns = [
        "order_id",
        "order_item_id",
        "order_purchase_timestamp",
        "purchase_month",
        "customer_unique_id",
        "customer_city",
        "customer_state",
        "customer_region",
        "product_id",
        "product_category",
        "seller_id",
        "item_revenue",
        "freight_value",
    ]
    sales = sales[output_columns].sort_values(
        ["order_purchase_timestamp", "order_id", "order_item_id"]
    )

    duplicated_item_keys = int(sales.duplicated(["order_id", "order_item_id"]).sum())
    if duplicated_item_keys:
        raise ValueError(
            f"Unexpected duplicate order-item keys after joins: {duplicated_item_keys}"
        )

    q1 = float(sales["item_revenue"].quantile(0.25))
    q3 = float(sales["item_revenue"].quantile(0.75))
    upper_iqr = q3 + 1.5 * (q3 - q1)

    stats: dict[str, int | float] = {
        "raw_exact_duplicates": int(
            sum(frame.duplicated().sum() for frame in raw.values())
        ),
        "invalid_price_or_freight_rows": int(len(items) - len(valid_items)),
        "non_delivered_orders_excluded": int((~orders["order_status"].eq("delivered")).sum()),
        "delivered_orders_outside_analysis_window": int(
            (
                orders["order_status"].eq("delivered")
                & (
                    orders["order_purchase_timestamp"].lt(start)
                    | orders["order_purchase_timestamp"].ge(end_exclusive)
                    | orders["order_purchase_timestamp"].isna()
                )
            ).sum()
        ),
        "missing_category_item_rows": int(sales["product_category"].eq("unknown").sum()),
        "unknown_region_item_rows": int(sales["customer_region"].eq("Unknown").sum()),
        "price_outlier_upper_iqr_brl": round(upper_iqr, 2),
        "price_outlier_item_rows_retained": int(sales["item_revenue"].gt(upper_iqr).sum()),
    }
    return sales.reset_index(drop=True), stats


def calculate_metrics(sales: pd.DataFrame) -> dict[str, int | float | None]:
    """Calculate order-level metrics; undefined rates are None for empty data."""
    order_values = sales.groupby("order_id", as_index=False).agg(
        order_revenue=("item_revenue", "sum"),
        customer_unique_id=("customer_unique_id", "first"),
    )
    customer_orders = order_values.groupby("customer_unique_id")["order_id"].nunique()

    total_revenue = float(order_values["order_revenue"].sum())
    total_orders = int(order_values["order_id"].nunique())
    unique_customers = int(customer_orders.size)
    repeat_customers = int(customer_orders.gt(1).sum())

    return {
        "total_revenue_brl": round(total_revenue, 2),
        "orders": total_orders,
        "items": int(len(sales)),
        "average_order_value_brl": (
            round(total_revenue / total_orders, 2) if total_orders else None
        ),
        "unique_customers": unique_customers,
        "repeat_customers": repeat_customers,
        "repeat_customer_rate_pct": (
            round(100 * repeat_customers / unique_customers, 2)
            if unique_customers else None
        ),
    }


def build_summary_tables(sales: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build the tables used in charts and the README."""
    monthly = (
        sales.groupby("purchase_month", as_index=False)
        .agg(
            revenue_brl=("item_revenue", "sum"),
            orders=("order_id", "nunique"),
            items=("order_item_id", "size"),
        )
        .sort_values("purchase_month")
    )
    monthly["average_order_value_brl"] = monthly["revenue_brl"] / monthly["orders"]

    categories = (
        sales.groupby("product_category", as_index=False)
        .agg(
            revenue_brl=("item_revenue", "sum"),
            orders=("order_id", "nunique"),
            items=("order_item_id", "size"),
        )
        .sort_values("revenue_brl", ascending=False)
    )
    categories["revenue_share_pct"] = (
        100 * categories["revenue_brl"] / categories["revenue_brl"].sum()
    )

    regions = (
        sales.groupby("customer_region", as_index=False)
        .agg(
            revenue_brl=("item_revenue", "sum"),
            orders=("order_id", "nunique"),
            customers=("customer_unique_id", "nunique"),
        )
        .sort_values("revenue_brl", ascending=False)
    )
    regions["revenue_share_pct"] = 100 * regions["revenue_brl"] / regions["revenue_brl"].sum()

    products = (
        sales.groupby(["product_id", "product_category"], as_index=False)
        .agg(
            revenue_brl=("item_revenue", "sum"),
            orders=("order_id", "nunique"),
            items_sold=("order_item_id", "size"),
        )
        .sort_values(["items_sold", "revenue_brl"], ascending=[False, False])
    )

    return {
        "monthly_sales": monthly,
        "category_sales": categories,
        "region_sales": regions,
        "top_products": products.head(20),
    }


def build_cohort_retention(
    sales: pd.DataFrame,
    end_exclusive: pd.Timestamp = ANALYSIS_END_EXCLUSIVE,
    horizon_months: int = 6,
) -> pd.DataFrame:
    """Return six-month repeat-purchase retention for fully observed cohorts."""
    columns = [
        "cohort_month",
        "months_since_first_order",
        "customers",
        "cohort_size",
        "retention_pct",
    ]
    if horizon_months < 1:
        raise ValueError("horizon_months must be positive")
    if sales.empty:
        return pd.DataFrame(columns=columns)

    order_months = sales[["order_id", "customer_unique_id", "purchase_month"]].drop_duplicates(
        ["order_id", "customer_unique_id"]
    )
    order_months["month"] = pd.PeriodIndex(order_months["purchase_month"], freq="M")
    first_month = order_months.groupby("customer_unique_id")["month"].min()
    order_months = order_months.join(first_month.rename("cohort_month"), on="customer_unique_id")
    last_complete_month = pd.Period(end_exclusive - pd.Timedelta(days=1), freq="M")
    latest_cohort = last_complete_month - (horizon_months - 1)
    order_months = order_months[order_months["cohort_month"].le(latest_cohort)]
    if order_months.empty:
        return pd.DataFrame(columns=columns)

    order_months["months_since_first_order"] = (
        (order_months["month"].dt.year - order_months["cohort_month"].dt.year) * 12
        + order_months["month"].dt.month - order_months["cohort_month"].dt.month
    )
    eligible_first_months = first_month[first_month.le(latest_cohort)]
    cohort_sizes = eligible_first_months.groupby(eligible_first_months).size()
    active = order_months[
        order_months["months_since_first_order"].between(0, horizon_months - 1)
    ]
    active_counts = active.groupby(
        ["cohort_month", "months_since_first_order"]
    )["customer_unique_id"].nunique()

    rows = []
    for cohort, cohort_size in cohort_sizes.items():
        for age in range(horizon_months):
            customers = int(active_counts.get((cohort, age), 0))
            rows.append(
                {
                    "cohort_month": str(cohort),
                    "months_since_first_order": age,
                    "customers": customers,
                    "cohort_size": int(cohort_size),
                    "retention_pct": round(100 * customers / cohort_size, 2),
                }
            )
    return pd.DataFrame(rows, columns=columns)


def build_quality_report(stats: Mapping[str, int | float]) -> pd.DataFrame:
    """Describe checks, counts, and decisions taken during cleaning."""
    rows = [
        ("Exact duplicate source rows", stats["raw_exact_duplicates"], "Removed before joins"),
        (
            "Negative price or freight rows",
            stats["invalid_price_or_freight_rows"],
            "Excluded as logically invalid",
        ),
        (
            "Orders not marked delivered",
            stats["non_delivered_orders_excluded"],
            "Excluded from realized sales",
        ),
        (
            "Delivered orders outside 2017-01 to 2018-08",
            stats["delivered_orders_outside_analysis_window"],
            "Excluded to keep complete comparable months",
        ),
        (
            "Item rows without translated product category",
            stats["missing_category_item_rows"],
            "Retained and labeled unknown",
        ),
        (
            "Item rows without mapped macro-region",
            stats["unknown_region_item_rows"],
            "Retained and labeled Unknown",
        ),
        (
            f"Item prices above IQR threshold (BRL {stats['price_outlier_upper_iqr_brl']})",
            stats["price_outlier_item_rows_retained"],
            "Flagged and retained; high prices can be valid sales",
        ),
    ]
    return pd.DataFrame(rows, columns=["check", "row_count", "treatment"])


def save_cohort_figure(cohort_retention: pd.DataFrame, image_path: Path) -> None:
    """Save the six-month retention heatmap without rebuilding other charts."""
    if cohort_retention.empty:
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    cohort_matrix = cohort_retention.pivot(
        index="cohort_month", columns="months_since_first_order", values="retention_pct"
    )
    fig, ax = plt.subplots(figsize=(10, max(4, len(cohort_matrix) * 0.34)))
    sns.heatmap(
        cohort_matrix,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        vmin=0,
        vmax=100,
        cbar_kws={"label": "Customers with a delivered order (%)"},
        ax=ax,
    )
    ax.set_title(
        "Six-month repeat-purchase retention by first-order cohort",
        loc="left",
        weight="bold",
    )
    ax.set_xlabel("Months since first delivered order")
    ax.set_ylabel("First-order month")
    fig.tight_layout()
    fig.savefig(image_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_figures(
    tables: Mapping[str, pd.DataFrame],
    image_dir: Path,
    cohort_retention: pd.DataFrame | None = None,
) -> None:
    """Create consistent portfolio-ready charts."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    image_dir.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", font_scale=0.95)
    accent = "#2563EB"
    secondary = "#0F766E"

    monthly = tables["monthly_sales"].copy()
    fig, ax = plt.subplots(figsize=(11, 5.5))
    sns.lineplot(data=monthly, x="purchase_month", y="revenue_brl", marker="o", color=accent, ax=ax)
    ax.set_title("Monthly merchandise revenue", loc="left", weight="bold")
    ax.set_xlabel("Purchase month")
    ax.set_ylabel("Revenue (BRL)")
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value / 1_000_000:.1f}M")
    sns.despine()
    fig.tight_layout()
    fig.savefig(image_dir / "monthly_revenue.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    categories = tables["category_sales"].head(10).sort_values("revenue_brl")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=categories, x="revenue_brl", y="product_category", color=secondary, ax=ax)
    ax.set_title("Top 10 product categories by revenue", loc="left", weight="bold")
    ax.set_xlabel("Revenue (BRL)")
    ax.set_ylabel("")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value / 1_000_000:.1f}M")
    sns.despine()
    fig.tight_layout()
    fig.savefig(image_dir / "top_categories.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    regions = tables["region_sales"].sort_values("revenue_brl", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(data=regions, x="customer_region", y="revenue_brl", color=accent, ax=ax)
    ax.set_title("Revenue by Brazilian macro-region", loc="left", weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Revenue (BRL)")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value / 1_000_000:.1f}M")
    sns.despine()
    fig.tight_layout()
    fig.savefig(image_dir / "regional_sales.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    if cohort_retention is not None:
        save_cohort_figure(cohort_retention, image_dir / "cohort_retention.png")


def run_analysis(project_root: Path) -> dict[str, object]:
    """Run the complete pipeline and write all reproducible outputs."""
    raw_dir = project_root / "data" / "raw"
    processed_dir = project_root / "data" / "processed"
    image_dir = project_root / "images"
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw = load_raw_data(raw_dir)
    sales, stats = prepare_sales(raw)
    metrics = calculate_metrics(sales)
    tables = build_summary_tables(sales)
    cohort_retention = build_cohort_retention(sales)
    quality = build_quality_report(stats)

    sales.to_csv(processed_dir / "sales_analysis.csv", index=False)
    sales.head(1_000).to_csv(processed_dir / "sales_analysis_sample.csv", index=False)
    for name, table in tables.items():
        table.to_csv(processed_dir / f"{name}.csv", index=False)
    cohort_retention.to_csv(processed_dir / "cohort_retention.csv", index=False)
    quality.to_csv(processed_dir / "data_quality_summary.csv", index=False)

    metric_definitions = {
        "total_revenue_brl": "Sum of item prices for delivered orders; freight excluded",
        "orders": "Distinct delivered orders",
        "items": "Order-item rows",
        "average_order_value_brl": "Total merchandise revenue divided by distinct orders",
        "unique_customers": "Distinct customer_unique_id values",
        "repeat_customers": "Customers with more than one delivered order",
        "repeat_customer_rate_pct": "Repeat customers divided by unique customers",
    }
    metrics_frame = pd.DataFrame(
        [
            {"metric": key, "value": value, "definition": metric_definitions[key]}
            for key, value in metrics.items()
        ]
    )
    metrics_frame.to_csv(processed_dir / "analysis_metrics.csv", index=False)

    metadata = {
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end_inclusive": (ANALYSIS_END_EXCLUSIVE - pd.Timedelta(days=1)).date().isoformat(),
        "currency": "BRL",
        "revenue_definition": "Sum of item price; freight excluded",
        "grain": "One row per order item",
        "data_source": "Brazilian E-Commerce Public Dataset by Olist",
        "data_source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "data_license": "CC BY-NC-SA 4.0",
    }
    (processed_dir / "analysis_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    save_figures(tables, image_dir, cohort_retention)
    return {
        "metrics": metrics,
        "quality": stats,
        "tables": tables,
        "cohort_retention": cohort_retention,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    result = run_analysis(root)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))

