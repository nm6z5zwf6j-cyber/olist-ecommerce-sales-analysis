-- Olist e-commerce sales analysis
-- SQL dialect: SQLite
-- Analysis period: 2017-01-01 through 2018-08-31
-- Revenue definition: item price for delivered orders; freight excluded.

-- QUERY 1: Headline revenue, order count, and average order value
WITH delivered_sales AS (
    SELECT
        o.order_id,
        oi.order_item_id,
        oi.price
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
),
order_values AS (
    SELECT order_id, SUM(price) AS order_revenue
    FROM delivered_sales
    GROUP BY order_id
)
SELECT
    ROUND(SUM(order_revenue), 2) AS total_revenue_brl,
    COUNT(*) AS orders,
    ROUND(AVG(order_revenue), 2) AS average_order_value_brl
FROM order_values;

-- QUERY 2: Monthly revenue and order volume
WITH order_values AS (
    SELECT
        o.order_id,
        STRFTIME('%Y-%m', o.order_purchase_timestamp) AS purchase_month,
        SUM(oi.price) AS order_revenue
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
    GROUP BY o.order_id, purchase_month
)
SELECT
    purchase_month,
    ROUND(SUM(order_revenue), 2) AS revenue_brl,
    COUNT(*) AS orders,
    ROUND(AVG(order_revenue), 2) AS average_order_value_brl
FROM order_values
GROUP BY purchase_month
ORDER BY purchase_month;

-- QUERY 3: Product categories ranked by revenue
SELECT
    COALESCE(t.product_category_name_english, 'unknown') AS product_category,
    ROUND(SUM(oi.price), 2) AS revenue_brl,
    COUNT(DISTINCT o.order_id) AS orders,
    COUNT(*) AS items
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
LEFT JOIN products AS p ON p.product_id = oi.product_id
LEFT JOIN category_translation AS t
    ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
  AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
  AND DATE(o.order_purchase_timestamp) < '2018-09-01'
  AND oi.price >= 0
  AND oi.freight_value >= 0
GROUP BY product_category
ORDER BY revenue_brl DESC
LIMIT 10;

-- QUERY 4: Revenue by Brazilian macro-region
WITH regional_sales AS (
    SELECT
        o.order_id,
        oi.price,
        CASE
            WHEN c.customer_state IN ('AC', 'AP', 'AM', 'PA', 'RO', 'RR', 'TO') THEN 'North'
            WHEN c.customer_state IN ('AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE') THEN 'Northeast'
            WHEN c.customer_state IN ('DF', 'GO', 'MT', 'MS') THEN 'Central-West'
            WHEN c.customer_state IN ('ES', 'MG', 'RJ', 'SP') THEN 'Southeast'
            WHEN c.customer_state IN ('PR', 'RS', 'SC') THEN 'South'
            ELSE 'Unknown'
        END AS customer_region
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
)
SELECT
    customer_region,
    ROUND(SUM(price), 2) AS revenue_brl,
    COUNT(DISTINCT order_id) AS orders
FROM regional_sales
GROUP BY customer_region
ORDER BY revenue_brl DESC;

-- QUERY 5: Most frequently purchased anonymized products
SELECT
    oi.product_id,
    COALESCE(t.product_category_name_english, 'unknown') AS product_category,
    COUNT(*) AS items_sold,
    COUNT(DISTINCT o.order_id) AS orders,
    ROUND(SUM(oi.price), 2) AS revenue_brl
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.order_id
LEFT JOIN products AS p ON p.product_id = oi.product_id
LEFT JOIN category_translation AS t
    ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
  AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
  AND DATE(o.order_purchase_timestamp) < '2018-09-01'
  AND oi.price >= 0
  AND oi.freight_value >= 0
GROUP BY oi.product_id, product_category
ORDER BY items_sold DESC, revenue_brl DESC
LIMIT 20;

-- QUERY 6: Repeat-customer rate
WITH customer_orders AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*) AS unique_customers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(
        100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0),
        2
    ) AS repeat_customer_rate_pct
FROM customer_orders;

-- QUERY 7: Month-over-month revenue growth using a window function
WITH monthly_sales AS (
    SELECT
        STRFTIME('%Y-%m', o.order_purchase_timestamp) AS purchase_month,
        SUM(oi.price) AS revenue_brl
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
    GROUP BY purchase_month
),
monthly_with_previous AS (
    SELECT
        purchase_month,
        revenue_brl,
        LAG(revenue_brl) OVER (ORDER BY purchase_month) AS previous_month_revenue
    FROM monthly_sales
)
SELECT
    purchase_month,
    ROUND(revenue_brl, 2) AS revenue_brl,
    ROUND(
        100.0 * (revenue_brl - previous_month_revenue)
        / NULLIF(previous_month_revenue, 0),
        2
    ) AS month_over_month_growth_pct
FROM monthly_with_previous
ORDER BY purchase_month;

-- QUERY 8: Highest-revenue category within each macro-region
WITH category_region_sales AS (
    SELECT
        CASE
            WHEN c.customer_state IN ('AC', 'AP', 'AM', 'PA', 'RO', 'RR', 'TO') THEN 'North'
            WHEN c.customer_state IN ('AL', 'BA', 'CE', 'MA', 'PB', 'PE', 'PI', 'RN', 'SE') THEN 'Northeast'
            WHEN c.customer_state IN ('DF', 'GO', 'MT', 'MS') THEN 'Central-West'
            WHEN c.customer_state IN ('ES', 'MG', 'RJ', 'SP') THEN 'Southeast'
            WHEN c.customer_state IN ('PR', 'RS', 'SC') THEN 'South'
            ELSE 'Unknown'
        END AS customer_region,
        COALESCE(t.product_category_name_english, 'unknown') AS product_category,
        SUM(oi.price) AS revenue_brl
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN order_items AS oi ON oi.order_id = o.order_id
    LEFT JOIN products AS p ON p.product_id = oi.product_id
    LEFT JOIN category_translation AS t
        ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
      AND DATE(o.order_purchase_timestamp) >= '2017-01-01'
      AND DATE(o.order_purchase_timestamp) < '2018-09-01'
      AND oi.price >= 0
      AND oi.freight_value >= 0
    GROUP BY customer_region, product_category
),
ranked_categories AS (
    SELECT
        customer_region,
        product_category,
        revenue_brl,
        DENSE_RANK() OVER (
            PARTITION BY customer_region
            ORDER BY revenue_brl DESC
        ) AS revenue_rank
    FROM category_region_sales
)
SELECT
    customer_region,
    product_category,
    ROUND(revenue_brl, 2) AS revenue_brl
FROM ranked_categories
WHERE revenue_rank = 1
ORDER BY revenue_brl DESC;

