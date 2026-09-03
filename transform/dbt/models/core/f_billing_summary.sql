{{ config(
    materialized = 'table',
    tags = ['core', 'billing']
) }}

-- Billing Summary Gold Layer
-- Monthly billing aggregation and revenue tracking

WITH monthly_billing AS (
    SELECT
        customer_id,
        hashed_id,
        plan_id,
        billing_month,
        base_charge,
        usage_charge,
        total_charge,
        payment_status,
        payment_method,
        ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY billing_month DESC) as rn
    FROM {{ ref('stg_billing_monthly') }}
),
customer_summary AS (
    SELECT
        customer_id,
        MAX(CASE WHEN billing_month = (SELECT MAX(billing_month) FROM monthly_billing) THEN total_charge END) as current_month_charge,
        AVG(total_charge) as avg_monthly_charge,
        SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) as paid_months,
        SUM(CASE WHEN payment_status = 'overdue' THEN 1 ELSE 0 END) as overdue_months,
        SUM(CASE WHEN payment_status = 'defaulted' THEN 1 ELSE 0 END) as defaulted_months,
        COUNT(DISTINCT billing_month) as num_billing_months
    FROM monthly_billing
    GROUP BY customer_id
),
revenue_by_plan AS (
    SELECT
        b.plan_id,
        p.name as plan_name,
        p.type as plan_type,
        COUNT(DISTINCT b.customer_id) as subscriber_count,
        SUM(b.current_month_charge) as total_revenue,
        AVG(b.current_month_charge) as avg_revenue_per_user,
        SUM(CASE WHEN cs.paid_months = cs.num_billing_months THEN 1 ELSE 0 END) as fully_paid_customers,
        SUM(CASE WHEN cs.defaulted_months > 0 THEN 1 ELSE 0 END) as defaulted_customers
    FROM customer_summary cs
    JOIN {{ ref('stg_billing') }} b ON cs.customer_id = b.customer_id
    LEFT JOIN {{ ref('dim_plans') }} p ON b.plan_id = p.plan_id
    GROUP BY b.plan_id, p.name, p.type
)

SELECT
    customer_id,
    hashed_id,
    plan_id,
    current_month_charge,
    avg_monthly_charge,
    paid_months,
    overdue_months,
    defaulted_months,
    num_billing_months,
    CASE
        WHEN defaulted_months > 0 THEN 'defaulted'
        WHEN overdue_months > 0 THEN 'at_risk'
        WHEN paid_months = num_billing_months THEN 'good_standing'
        ELSE 'needs_attention'
    END as payment_health,
    CURRENT_TIMESTAMP as gold_ingestion_timestamp
FROM customer_summary

UNION ALL

SELECT
    NULL as customer_id,
    NULL as hashed_id,
    plan_id,
    NULL as current_month_charge,
    avg_revenue_per_user as avg_monthly_charge,
    fully_paid_customers as paid_months,
    NULL as overdue_months,
    defaulted_customers as defaulted_months,
    subscriber_count as num_billing_months,
    NULL as payment_health,
    CURRENT_TIMESTAMP as gold_ingestion_timestamp
FROM revenue_by_plan
