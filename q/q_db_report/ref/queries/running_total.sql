WITH daily AS (
    SELECT o.ordered_at AS day, SUM(i.qty * i.unit_price) AS revenue
    FROM orders o JOIN order_items i ON i.order_id = o.id
    WHERE o.status = 'paid'
    GROUP BY o.ordered_at
)
SELECT day, revenue, SUM(revenue) OVER (ORDER BY day ROWS UNBOUNDED PRECEDING) AS running_total
FROM daily
ORDER BY day;
