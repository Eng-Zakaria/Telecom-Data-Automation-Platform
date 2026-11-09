SELECT subscriber_key, total_estimated_leakage
FROM {{ ref('f_revenue_leakage') }}
WHERE total_estimated_leakage < 0
