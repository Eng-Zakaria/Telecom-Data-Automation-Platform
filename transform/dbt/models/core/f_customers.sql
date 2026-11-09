{{ config(
    materialized = 'table',
    tags = ['core', 'customer']
) }}

-- Customer 360 Gold Layer
-- Unified customer view joining all source systems

WITH billing_base AS (
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
        lifetime_value,
        subscriber_key,
        1 as rn  -- stg_billing holds exactly one current account per subscriber
    FROM {{ ref('stg_billing') }}
),
cdr_agg AS (
    SELECT
        subscriber_key,
        COUNT(*) as total_calls,
        SUM(CASE WHEN call_type = 'voice' THEN 1 ELSE 0 END) as voice_calls,
        SUM(CASE WHEN call_type = 'sms' THEN 1 ELSE 0 END) as sms_count,
        SUM(CASE WHEN call_type = 'data' THEN 1 ELSE 0 END) as data_sessions,
        SUM(duration_seconds) as total_call_duration_sec,
        SUM(data_volume_mb) as total_data_mb,
        AVG(signal_strength_dbm) as avg_signal_strength,
        MAX(start_time) as last_activity
    FROM {{ ref('stg_cdr') }}
    WHERE start_time >= ({{ as_of_date() }} - INTERVAL 90 DAY)
    GROUP BY subscriber_key
),
support_agg AS (
    SELECT
        subscriber_key,
        COUNT(*) as total_complaints,
        SUM(CASE WHEN resolved = true THEN 1 ELSE 0 END) as resolved_complaints,
        AVG(resolution_time_days) as avg_resolution_time,
        MAX(posted_date) as last_complaint_date
    FROM {{ ref('stg_complaints') }}
    WHERE posted_date <= {{ as_of_date() }} + INTERVAL 1 DAY
      AND posted_date >= ({{ as_of_date() }} - INTERVAL 180 DAY)
    GROUP BY subscriber_key
),
roaming_agg AS (
    SELECT
        subscriber_key,
        COUNT(*) as roaming_sessions,
        SUM(voice_minutes) as total_roaming_minutes,
        SUM(data_mb) as total_roaming_data_mb,
        SUM(settlement_amount) as total_roaming_cost,
        MAX(start_time) as last_roaming_date
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= ({{ as_of_date() }} - INTERVAL 90 DAY)
    GROUP BY subscriber_key
),
churn_flags AS (
    SELECT
        customer_id,
        CASE
            WHEN tenure_days < 90 THEN 'new'
            WHEN tenure_days < 365 THEN 'recent'
            WHEN tenure_days < 730 THEN 'established'
            ELSE 'loyal'
        END as tenure_segment,
        CASE
            WHEN lifetime_value > 5000 THEN 'high_value'
            WHEN lifetime_value > 2000 THEN 'medium_value'
            ELSE 'low_value'
        END as value_segment,
        CASE
            WHEN payment_status = 'defaulted' THEN 'at_risk'
            WHEN payment_status = 'overdue' THEN 'concern'
            ELSE 'good'
        END as payment_health
    FROM billing_base
    WHERE rn = 1
)

SELECT
    b.customer_id,
    b.hashed_id,
    b.subscriber_key,
    b.plan_id,
    p.plan_name,
    p.plan_type,
    b.monthly_charge,
    b.usage_charges,
    b.total_charge,
    b.payment_status,
    b.payment_method,
    b.tenure_days,
    b.contract_start,
    b.contract_end,
    b.lifetime_value,
    c.total_calls,
    c.voice_calls,
    c.sms_count,
    c.data_sessions,
    c.total_call_duration_sec,
    c.total_data_mb,
    c.avg_signal_strength,
    c.last_activity,
    s.total_complaints,
    s.resolved_complaints,
    s.avg_resolution_time,
    s.last_complaint_date,
    r.roaming_sessions,
    r.total_roaming_minutes,
    r.total_roaming_data_mb,
    r.total_roaming_cost,
    r.last_roaming_date,
    t.tenure_segment,
    t.value_segment,
    t.payment_health,
    CASE
        WHEN s.total_complaints > 3 AND t.payment_health = 'at_risk' THEN 'high_churn_risk'
        WHEN s.total_complaints > 1 AND t.payment_health = 'concern' THEN 'medium_churn_risk'
        WHEN t.payment_health = 'at_risk' THEN 'low_churn_risk'
        ELSE 'low_churn_risk'
    END as churn_risk_level,
    CASE
        WHEN c.total_calls > 100 AND c.total_data_mb > 1000 THEN 'heavy_user'
        WHEN c.total_calls > 50 THEN 'regular_user'
        ELSE 'light_user'
    END as usage_segment,
    CURRENT_TIMESTAMP as gold_ingestion_timestamp
FROM billing_base b
LEFT JOIN {{ ref('dim_plans') }} p ON b.plan_id = p.plan_id
-- every feed is joined on the pseudonymous subscriber key (sha256(customer_id)[:16])
LEFT JOIN cdr_agg c ON b.subscriber_key = c.subscriber_key
LEFT JOIN support_agg s ON b.subscriber_key = s.subscriber_key
LEFT JOIN roaming_agg r ON b.subscriber_key = r.subscriber_key
LEFT JOIN churn_flags t ON b.customer_id = t.customer_id
WHERE b.rn = 1
