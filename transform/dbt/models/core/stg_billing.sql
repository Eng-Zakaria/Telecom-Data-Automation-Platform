{{ config(
    materialized = 'view',
    tags = ['staging', 'billing']
) }}

-- Staging layer for Billing data
-- Cleans and standardizes billing records

SELECT
    customer_id,
    hashed_id,
    plan_id,
    contract_start,
    contract_end,
    tenure_days,
    monthly_charge,
    usage_charges,
    total_charge,
    payment_status,
    payment_method,
    last_payment_date,
    num_overdue_months,
    lifetime_value,
    CASE
        WHEN payment_status = 'paid' AND last_payment_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY) THEN 'current'
        WHEN payment_status = 'overdue' AND num_overdue_months <= 1 THEN 'behind'
        WHEN payment_status = 'overdue' AND num_overdue_months > 1 THEN 'serious'
        WHEN payment_status = 'defaulted' THEN 'defaulted'
        ELSE 'unknown'
    END as payment_health_category,
    CASE
        WHEN lifetime_value > 5000 THEN 'high_value'
        WHEN lifetime_value > 2000 THEN 'medium_value'
        ELSE 'low_value'
    END as customer_value_segment,
    CASE
        WHEN tenure_days < 90 THEN 'new_customer'
        WHEN tenure_days < 365 THEN 'recent'
        WHEN tenure_days < 730 THEN 'established'
        ELSE 'loyal'
    END as tenure_segment,
    CURRENT_TIMESTAMP as staging_ingestion_timestamp
FROM {{ source('bronze', 'billing_raw') }}
WHERE customer_id IS NOT NULL
