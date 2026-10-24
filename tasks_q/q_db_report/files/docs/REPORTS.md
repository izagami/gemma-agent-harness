# Reports

Each report is one SELECT in `queries/<name>.sql`, run by `python3 report.py DB <name>`.
Column names (exactly as below, in this order), row order and values are part of the spec.

Common rules:
* Revenue = SUM(qty * unit_price) over order_items. Only orders with status `paid` count; `cancelled` orders never count.
* Products marked `deleted` still count (they were sold back then).
* Guest orders (`customer_id` NULL) count for revenue totals but belong to no customer.
* Months are `YYYY-MM` text; days are `YYYY-MM-DD` text, as stored.

## monthly_category_revenue
Columns: `month`, `category`, `revenue`.
One row for every month from the month of the first paid order to the month of the last paid order (inclusive, no gaps)
times every category (also categories that never sold). `revenue` is 0 when nothing was sold. Order: month, category name.

## top_customers_by_region
Columns: `region`, `rank`, `customer`, `total`.
`total` = paid revenue of the customer; customers with no paid revenue are not listed. Customers without a region are
grouped under the region `(none)`. `rank` is the dense rank by total, highest first, within the region (equal totals
share a rank, the next rank is +1). Keep ranks 1 to 3 (ties can give more than 3 rows). Order: region, rank, customer name.

## customers_without_orders
Columns: `id`, `name`. Customers that have no paid order (customers whose orders were all cancelled are included).
Order: id.

## running_total
Columns: `day`, `revenue`, `running_total`. One row per day that has paid revenue: the revenue of that day and the
sum of all daily revenue up to and including that day. Order: day.
