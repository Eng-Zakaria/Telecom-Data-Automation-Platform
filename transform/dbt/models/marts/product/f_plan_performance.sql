{{ config(
    materialized = 'table',
    tags = ['marts', 'product', 'plans']
) }}

-- Plan Performance Analysis
-- Tracks plan adoption, migration patterns, and revenue contribution

WITH plan_metrics AS (
    SELECT
        p.plan_id,
        p.name as plan_name,
        p.type as plan_type,
        p.monthly_fee,
        p.included_minutes,
        p.included_sms,
        p.included_data_gb,
        p.roaming_enabled,
        COUNT(DISTINCT b.customer_id) as active_subscribers,
        SUM(b.total_charge) as total_revenue,
        AVG(b.total_charge) as avg_revenue_per_user,
        SUM(CASE WHEN b.payment_status = 'paid' THEN 1 ELSE 0 END) as paying_customers,
        SUM(CASE WHEN b.payment_status = 'overdue' THEN 1 ELSE 0 END) as overdue_customers,
        SUM(CASE WHEN b.payment_status = 'defaulted' THEN 1 ELSE 0 END) as defaulted_customers,
        AVG(b.tenure_days) as avg_tenure,
        AVG(b.lifetime_value) as avg_lifetime_value
    FROM {{ ref('dim_plans') }} p
    LEFT JOIN {{ ref('stg_billing') }} b ON p.plan_id = b.plan_id
    WHERE b.is_current = true
    GROUP BY p.plan_id, p.name, p.type, p.monthly_fee,
             p.included_minutes, p.included_sms, p.included_data_gb, p.roaming_enabled
),
migration_patterns AS (
    SELECT
        b1.plan_id as from_plan,
        p1.name as from_plan_name,
        b2.plan_id as to_plan,
        p2.name as to_plan_name,
        COUNT(*) as migration_count,
        AVG(b2.tenure_days - b1.tenure_days) as avg_days_in_previous_plan,
        SUM(CASE WHEN b2.total_charge > b1.total_charge THEN 1 ELSE 0 END) as upgraded_count,
        SUM(CASE WHEN b2.total_charge < b1.total_charge THEN 1 ELSE 0 END) as downgraded_count
    FROM {{ ref('stg_billing') }} b1
    JOIN {{ ref('stg_billing_history') }} b2 ON b1.customer_id = b2.customer_id
        AND b2.billing_month = DATE_ADD(b1.billing_month, INTERVAL 1 MONTH)
    JOIN {{ ref('dim_plans') }} p1 ON b1.plan_id = p1.plan_id
    JOIN {{ ref('dim_plans') }} p2 ON b2.plan_id = p2.plan_id
    WHERE b1.billing_month = DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 2 MONTH), '%Y-%m')
    GROUP BY b1.plan_id, p1.name, b2.plan_id, p2.name
),
plan_comparison AS (
    SELECT
        plan_id,
        plan_name,
        plan_type,
        monthly_fee,
        active_subscribers,
        total_revenue,
        avg_revenue_per_user,
        paying_customers * 100.0 / NULLIF(active_subscribers, 0) as payment_rate,
        (defaulted_customers * 100.0 / NULLIF(active_subscribers, 0)) as default_rate,
        avg_tenure,
        avg_lifetime_value,
        ROW_NUMBER() OVER (ORDER BY total_revenue DESC) as revenue_rank,
        ROW_NUMBER() OVER (ORDER BY active_subscribers DESC) as popularity_rank
    FROM plan_metrics
),
bundle_performance AS (
    SELECT
        p.plan_id,
        COUNT(DISTINCT CASE WHEN c.data_sessions > 0 THEN c.customer_id END) as data_users,
        COUNT(DISTINCT CASE WHEN c.voice_calls > 50 THEN c.customer_id END) as voice_heavy_users,
        COUNT(DISTINCT CASE WHEN c.roaming_sessions > 0 THEN c.customer_id END) as roaming_users,
        AVG(c.total_data_mb) as avg_data_usage,
        AVG(c.total_calls) as avg_call_volume
    FROM {{ ref('dim_plans') }} p
    JOIN {{ ref('stg_billing') }} b ON p.plan_id = b.plan_id
    JOIN {{ ref('f_customers') }} c ON b.customer_id = c.customer_id
    WHERE b.is_current = true
    GROUP BY p.plan_id
)

SELECT
    'plan_overview' as analysis_type,
    pc.plan_id,
    pc.plan_name,
    pc.plan_type,
    pc.monthly_fee,
    pc.active_subscribers,
    pc.total_revenue,
    pc.avg_revenue_per_user,
    pc.payment_rate,
    pc.default_rate,
    pc.avg_tenure,
    pc.avg_lifetime_value,
    pc.revenue_rank,
    pc.popularity_rank,
    bp.data_users,
    bp.voice_heavy_users,
    bp.roaming_users,
    bp.avg_data_usage,
    bp.avg_call_volume
FROM plan_comparison pc
LEFT JOIN bundle_performance bp ON pc.plan_id = bp.plan_id

UNION ALL

SELECT
    'migration_analysis' as analysis_type,
    mp.from_plan as plan_id,
    mp.from_plan_name as plan_name,
    NULL as plan_type,
    NULL as monthly_fee,
    mp.migration_count as active_subscribers,
    NULL as total_revenue,
    NULL as avg_revenue_per_user,
    NULL as payment_rate,
    NULL as default_rate,
    mp.avg_days_in_previous_plan as avg_tenure,
    NULL as avg_lifetime_value,
    NULL as revenue_rank,
    NULL as popularity_rank,
    mp.upgraded_count as data_users,
    mp.downgraded_count as voice_heavy_users,
    NULL as roaming_users,
    NULL as avg_data_usage,
    NULL as avg_call_volume
FROM migration_patterns mp
