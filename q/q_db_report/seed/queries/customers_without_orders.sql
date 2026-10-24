-- customers who never ordered
SELECT id, name
FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders)
ORDER BY id;
