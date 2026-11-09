-- Guards against the original defect: joins that compile but match nothing.
-- At least 90% of subscribers must carry CDR usage in the customer 360.
SELECT share FROM (
    SELECT avg(CASE WHEN total_calls IS NOT NULL THEN 1.0 ELSE 0 END) AS share
    FROM {{ ref('f_customers') }}
) WHERE share < 0.9
