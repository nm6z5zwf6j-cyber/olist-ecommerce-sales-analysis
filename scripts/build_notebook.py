"""Build the portfolio notebook with explanatory text and executable cells."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


def build_notebook(output_path: Path) -> None:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python", "version": "3.12"},
    }

    cells = [
        nbf.v4.new_markdown_cell(
            """# Анализ продаж Olist

Учебный портфолио-проект Junior Data Analyst на открытых анонимизированных данных бразильской торговой площадки Olist.

**Период анализа:** январь 2017 — август 2018.  
**Выручка:** сумма стоимости товаров в доставленных заказах без доставки.  
**Источник:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), лицензия CC BY-NC-SA 4.0.

Цель — проверить качество данных, собрать аналитическую витрину, рассчитать основные показатели и сформулировать выводы, которые непосредственно следуют из расчётов."""
        ),
        nbf.v4.new_code_cell(
            """from pathlib import Path
import sys

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

ROOT = Path.cwd()
if not (ROOT / "data").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))

from src.analysis import (
    build_quality_report,
    build_summary_tables,
    calculate_metrics,
    load_raw_data,
    prepare_sales,
    save_figures,
)

sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 20)
pd.set_option("display.float_format", lambda value: f"{value:,.2f}")"""
        ),
        nbf.v4.new_markdown_cell("## 1. Загрузка и первичная проверка данных"),
        nbf.v4.new_code_cell(
            """raw = load_raw_data(ROOT / "data" / "raw")

raw_overview = pd.DataFrame([
    {
        "table": name,
        "rows": len(frame),
        "columns": frame.shape[1],
        "exact_duplicates": int(frame.duplicated().sum()),
        "missing_cells": int(frame.isna().sum().sum()),
    }
    for name, frame in raw.items()
])
raw_overview"""
        ),
        nbf.v4.new_markdown_cell(
            """Пропуски в исходных таблицах не заменяются произвольными значениями. Для анализа продаж нужны дата покупки, статус заказа, покупатель, товар и цена. Недостающие переводы категорий сохраняются как `unknown`."""
        ),
        nbf.v4.new_markdown_cell("## 2. Очистка и объединение таблиц"),
        nbf.v4.new_code_cell(
            """sales, quality_stats = prepare_sales(raw)
quality_report = build_quality_report(quality_stats)

print(f"Строк в аналитической витрине: {len(sales):,}")
print(f"Уникальных заказов: {sales['order_id'].nunique():,}")
quality_report"""
        ),
        nbf.v4.new_markdown_cell(
            """Для сопоставимости месяцев используются доставленные заказы с 1 января 2017 года по 31 августа 2018 года. Дорогие товары, определённые правилом IQR, отмечены как выбросы, но не удалены: высокая цена сама по себе не доказывает ошибку."""
        ),
        nbf.v4.new_markdown_cell("## 3. Основные показатели"),
        nbf.v4.new_code_cell(
            """metrics = calculate_metrics(sales)
metrics_table = pd.DataFrame([
    ("Товарная выручка, BRL", metrics["total_revenue_brl"]),
    ("Доставленные заказы", metrics["orders"]),
    ("Проданные товарные позиции", metrics["items"]),
    ("Средний чек, BRL", metrics["average_order_value_brl"]),
    ("Уникальные покупатели", metrics["unique_customers"]),
    ("Повторные покупатели", metrics["repeat_customers"]),
    ("Доля повторных покупателей, %", metrics["repeat_customer_rate_pct"]),
], columns=["Показатель", "Значение"])
metrics_table"""
        ),
        nbf.v4.new_markdown_cell("## 4. Динамика продаж по месяцам"),
        nbf.v4.new_code_cell(
            """tables = build_summary_tables(sales)
monthly = tables["monthly_sales"].copy()

fig, ax = plt.subplots(figsize=(11, 5))
sns.lineplot(data=monthly, x="purchase_month", y="revenue_brl", marker="o", color="#2563EB", ax=ax)
ax.set_title("Товарная выручка по месяцам", loc="left", weight="bold")
ax.set_xlabel("Месяц покупки")
ax.set_ylabel("Выручка, BRL")
ax.tick_params(axis="x", rotation=45)
plt.tight_layout()
plt.show()

monthly.tail(8)"""
        ),
        nbf.v4.new_markdown_cell("## 5. Категории товаров"),
        nbf.v4.new_code_cell(
            """top_categories = tables["category_sales"].head(10).copy()

fig, ax = plt.subplots(figsize=(10, 6))
sns.barplot(
    data=top_categories.sort_values("revenue_brl"),
    x="revenue_brl",
    y="product_category",
    color="#0F766E",
    ax=ax,
)
ax.set_title("10 категорий с наибольшей выручкой", loc="left", weight="bold")
ax.set_xlabel("Выручка, BRL")
ax.set_ylabel("")
plt.tight_layout()
plt.show()

top_categories"""
        ),
        nbf.v4.new_markdown_cell("## 6. География продаж"),
        nbf.v4.new_code_cell(
            """regions = tables["region_sales"].copy()

fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(data=regions, x="customer_region", y="revenue_brl", color="#2563EB", ax=ax)
ax.set_title("Выручка по макрорегионам Бразилии", loc="left", weight="bold")
ax.set_xlabel("")
ax.set_ylabel("Выручка, BRL")
plt.tight_layout()
plt.show()

regions"""
        ),
        nbf.v4.new_markdown_cell("## 7. Наиболее продаваемые товары"),
        nbf.v4.new_code_cell(
            """tables["top_products"].head(10)"""
        ),
        nbf.v4.new_markdown_cell(
            """Названия товаров в датасете отсутствуют, поэтому рейтинг показывает анонимизированные `product_id` и соответствующие категории."""
        ),
        nbf.v4.new_markdown_cell(
            """## 8. Выводы

1. За выбранный период 96 211 доставленных заказов сформировали 13,18 млн BRL товарной выручки. Средний чек составил 137 BRL.
2. Выручка за январь–август 2018 года была на 141,1% выше, чем за те же месяцы 2017 года. Это описывает динамику выборки, но само по себе не объясняет причины роста.
3. Максимальная месячная выручка зафиксирована в ноябре 2017 года — 987,8 тыс. BRL. После этого в декабре показатель снизился на 26,5%.
4. Пять крупнейших категорий обеспечили 39,9% выручки. Лидер — `health_beauty` с долей 9,3%.
5. На Southeast пришлось 65,4% выручки, а на North — 2,5%. Продажи существенно сконцентрированы географически.
6. Повторными покупателями были 2 789 из 93 104 уникальных клиентов, или 3,0%.
7. 8 130 товарных строк превышают верхнюю границу IQR по цене. Они сохранены, поскольку без дополнительной проверки нельзя считать дорогие покупки ошибочными.

## 9. Рекомендации

1. Проверить сценарии второй покупки: послепродажные коммуникации, персональные предложения и сроки повторного заказа. Низкая доля повторных клиентов делает удержание отдельной зоной анализа.
2. Планировать запасы и продвижение с учётом концентрации выручки в пяти ведущих категориях, но контролировать зависимость от них.
3. Провести отдельный анализ причин ноябрьского пика и декабрьского снижения перед сезонным планированием. Данные показывают изменение, но не подтверждают его причину.
4. Тестировать региональные предложения за пределами Southeast и оценивать не только выручку, но также стоимость доставки и маржинальность, которых в текущем расчёте нет.
5. До решений по дорогим товарам проверить выбросы по первичным записям, категории и продавцу. Автоматически удалять их не следует.

## Ограничения

- В датасете нет себестоимости, поэтому рассчитана товарная выручка, а не прибыль.
- Стоимость доставки не включена в выручку.
- Данные относятся к Бразилии и периоду 2016–2018 годов; выводы нельзя автоматически переносить на текущий рынок.
- Наблюдаемые связи не доказывают причинность."""
        ),
        nbf.v4.new_code_cell(
            """# Сохраняем компактные таблицы и изображения, использованные в README.
save_figures(tables, ROOT / "images")
print("Анализ выполнен. Итоговые таблицы и графики сохранены.")"""
        ),
    ]

    notebook["cells"] = cells
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, output_path)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    build_notebook(root / "notebooks" / "analysis.ipynb")

