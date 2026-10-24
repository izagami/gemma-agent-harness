WITH RECURSIVE
paid AS (SELECT * FROM orders WHERE status = 'paid'),
bounds AS (SELECT substr(MIN(ordered_at), 1, 7) || '-01' AS lo, substr(MAX(ordered_at), 1, 7) || '-01' AS hi FROM paid),
months(m) AS (
    SELECT lo FROM bounds WHERE lo IS NOT NULL
    UNION ALL
    SELECT date(m, '+1 month') FROM months, bounds WHERE m < hi
),
sales AS (
    SELECT substr(o.ordered_at, 1, 7) AS month, p.category_id, SUM(i.qty * i.unit_price) AS revenue
    FROM paid o JOIN order_items i ON i.order_id = o.id JOIN products p ON p.id = i.product_id
    GROUP BY 1, 2
)
SELECT substr(months.m, 1, 7) AS month, c.name AS category, COALESCE(s.revenue, 0) AS revenue
FROM months CROSS JOIN categories c
LEFT JOIN sales s ON s.month = substr(months.m, 1, 7) AND s.category_id = c.id
ORDER BY month, category;
