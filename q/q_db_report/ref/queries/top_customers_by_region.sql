WITH totals AS (
    SELECT c.id, c.name, COALESCE(c.region, '(none)') AS region, SUM(i.qty * i.unit_price) AS total
    FROM customers c
    JOIN orders o ON o.customer_id = c.id AND o.status = 'paid'
    JOIN order_items i ON i.order_id = o.id
    GROUP BY c.id
    HAVING total > 0
), ranked AS (
    SELECT region, DENSE_RANK() OVER (PARTITION BY region ORDER BY total DESC) AS rank, name AS customer, total FROM totals
)
SELECT region, rank, customer, total FROM ranked WHERE rank <= 3 ORDER BY region, rank, customer;
