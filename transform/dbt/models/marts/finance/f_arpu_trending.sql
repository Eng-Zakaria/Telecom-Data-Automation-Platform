{{ config(
    materialized = 'table',
    tags = ['marts', 'finance', 'arpu']
) }}

-- ARPU/ARPAU Trending and Revenue Forecasting
-- Tracks average revenue per user and predicts future revenue

WITH monthly_revenue AS (
    SELECT
        billing_month,
        COUNT(DISTINCT customer_id) as active_customers,
        SUM(total_charge) as total_revenue,
        AVG(total_charge) as arpu,
        SUM(base_charge) as base_revenue,
        SUM(usage_charge) as usage_revenue,
        COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as paid_customers,
        COUNT(CASE WHEN payment_status = 'overdue' THEN 1 END) as overdue_customers,
        COUNT(CASE WHEN payment_status = 'defaulted' THEN 1 END) as defaulted_customers
    FROM {{ ref('stg_billing_monthly') }}
    GROUP BY billing_month
),
revenue_by_segment AS (
    SELECT
        cs.value_segment,
        cs.tenure_segment,
        billing_month,
        COUNT(DISTINCT cs.customer_id) as customers,
        SUM(b.total_charge) as revenue,
        AVG(b.total_charge) as segment_arpu,
        SUM(CASE WHEN b.payment_status = 'paid' THEN b.total_charge ELSE 0 END) as collected_revenue,
        SUM(CASE WHEN b.payment_status != 'paid' THEN b.total_charge ELSE 0 END) as uncollected_revenue
    FROM {{ ref('stg_billing') }} b
    JOIN {{ ref('f_customers') }} cs ON b.customer_id = cs.customer_id
    GROUP BY cs.value_segment, cs.tenure_segment, billing_month
),
revenue_by_plan AS (
    SELECT
        p.name as plan_name,
        p.type as plan_type,
        billing_month,
        COUNT(DISTINCT b.customer_id) as subscribers,
        SUM(b.total_charge) as revenue,
        AVG(b.total_charge) as plan_arpu,
        SUM(b.base_charge) as base_revenue,
        SUM(b.usage_charge) as usage_revenue
    FROM {{ ref('stg_billing') }} b
    JOIN {{ ref('dim_plans') }} p ON b.plan_id = p.plan_id
    GROUP BY p.name, p.type, billing_month
),
forecasting_data AS (
    SELECT
        billing_month,
        arpu,
        active_customers,
        total_revenue,
        -- Simple moving average forecast (3-month)
        AVG(arpu) OVER (ORDER BY billing_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as arpu_ma_3m,
        AVG(total_revenue) OVER (ORDER BY billing_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as revenue_ma_3m,
        -- Month-over-month growth
        LAG(arpu, 1) OVER (ORDER BY billing_month) as prev_arpu,
        LAG(total_revenue, 1) OVER (ORDER BY billing_month) as prev_revenue,
        (arpu - LAG(arpu, 1) OVER (ORDER BY billing_month)) / NULLIF(LAG(arpu, 1) OVER (ORDER BY billing_month), 0) as arpu_mom_growth,
        (total_revenue - LAG(total_revenue, 1) OVER (ORDER BY billing_month)) / NULLIF(LAG(total_revenue, 1) OVER (ORDER BY billing_month), 0) as revenue_mom_growth
    FROM monthly_revenue
)

SELECT
    'monthly_summary' as analysis_type,
    billing_month,
    active_customers,
    total_revenue,
    arpu,
    base_revenue,
    usage_revenue,
    paid_customers,
    overdue_customers,
    defaulted_customers,
    arpu_ma_3m,
    revenue_ma_3m,
    prev_arpu,
    prev_revenue,
    arpu_mom_growth,
    revenue_mom_growth,
    NULL as value_segment,
    NULL as tenure_segment,
    NULL as segment_arpu,
    NULL as plan_name,
    NULL as plan_type,
    NULL as subscribers
FROM monthly_revenue mr
LEFT JOIN forecasting_data fd ON mr.billing_month = fd.billing_month

UNION ALL

SELECT
    'segment_revenue' as analysis_type,
    billing_month,
    customers as active_customers,
    revenue as total_revenue,
    segment_arpu as arpu,
    NULL as base_revenue,
    NULL as usage_revenue,
    NULL as paid_customers,
    NULL as overdue_customers,
    NULL as defaulted_customers,
    NULL as arpu_ma_3m,
    NULL as revenue_ma_3m,
    NULL as prev_arpu,
    NULL as prev_revenue,
    NULL as arpu_mom_growth,
    NULL as revenue_mom_growth,
    value_segment,
    tenure_segment,
    segment_arpu,
    NULL as plan_name,
    NULL as plan_type,
    NULL as subscribers
FROM revenue_by_segment

UNION ALL

SELECT
    'plan_revenue' as analysis_type,
    billing_month,
    subscribers as active_customers,
    revenue as total_revenue,
    plan_arpu as arpu,
    base_revenue,
    usage_revenue,
    NULL as paid_customers,
    NULL as overdue_customers,
    NULL as defaulted_customers,
    NULL as arpu_ma_3m,
    NULL as revenue_ma_3m,
    NULL as prev_arpu,
    NULL as prev_revenue,
    NULL as arpu_mom_growth,
    NULL as revenue_mom_growth,
    NULL as value_segment,
    NULL as tenure_segment,
    NULL as segment_arpu,
    plan_name,
    plan_type,
    subscribers
FROM revenue_by_plan
