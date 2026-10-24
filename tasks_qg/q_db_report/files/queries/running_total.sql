-- revenue per day and the running total
SELECT o.ordered_at AS day,
       SUM(i.qty * i.unit_price) AS revenue,
       SUM(SUM(i.qty * i.unit_price)) OVER () AS running_total
FROM orders o JOIN order_items i ON i.order_id = o.id
GROUP BY o.ordered_at
ORDER BY day;
