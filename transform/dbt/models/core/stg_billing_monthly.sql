{{ config(materialized='view', tags=['staging', 'billing']) }}

-- One invoice per subscriber per month, enriched with the account's payment method.
SELECT
    m.customer_id,
    m.hashed_id,
    m.hashed_id                                           AS subscriber_key,
    m.plan_id,
    m.billing_month,
    CAST(strptime(m.billing_month || '-01', '%Y-%m-%d') AS DATE) AS billing_month_start,
    m.base_charge,
    m.usage_charge,
    m.total_charge,
    m.payment_status,
    b.payment_method,
    b.tenure_days
FROM {{ source('silver', 'billing_monthly') }} m
LEFT JOIN {{ source('silver', 'billing') }} b USING (customer_id)
WHERE m.customer_id IS NOT NULL
