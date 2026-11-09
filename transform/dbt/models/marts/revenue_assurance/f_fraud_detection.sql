{{ config(
    materialized = 'table',
    tags = ['marts', 'fraud', 'revenue_assurance']
) }}

-- Fraud Detection Model
-- Identifies suspicious patterns in CDR and billing data

WITH call_patterns AS (
    SELECT
        caller_id,
        callee_id,
        COUNT(*) as call_frequency,
        AVG(duration_seconds) as avg_duration,
        MIN(duration_seconds) as min_duration,
        MAX(duration_seconds) as max_duration,
        SUM(CASE WHEN duration_seconds < 10 THEN 1 ELSE 0 END) as very_short_calls,
        SUM(CASE WHEN duration_seconds > 300 THEN 1 ELSE 0 END) as long_calls,
        COUNT(DISTINCT CAST(start_time AS DATE)) as active_days,
        COUNT(DISTINCT cell_tower_id) as distinct_towers,
        AVG(signal_strength_dbm) as avg_signal_strength
    FROM {{ ref('stg_cdr') }}
    WHERE start_time >= ({{ as_of_date() }} - INTERVAL 30 DAY)
    GROUP BY caller_id, callee_id
    HAVING COUNT(*) > 5
),
roaming_patterns AS (
    SELECT
        subscriber_key,
        COUNT(*) as roaming_frequency,
        AVG(voice_minutes) as avg_roaming_minutes,
        SUM(settlement_amount) as total_roaming_cost,
        COUNT(DISTINCT partner_id) as distinct_partners,
        MAX(start_time) as last_roaming
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= ({{ as_of_date() }} - INTERVAL 30 DAY)
    GROUP BY subscriber_key
    HAVING COUNT(*) > 3
),
billing_anomalies AS (
    -- invoice spikes: usage far above the plan's base charge, using the monthly history
    SELECT
        subscriber_key,
        billing_month,
        total_charge,
        base_charge,
        usage_charge,
        (total_charge - base_charge) / NULLIF(base_charge, 0) as charge_variance,
        LAG(total_charge, 1) OVER (PARTITION BY subscriber_key ORDER BY billing_month) as prev_charge,
        LAG(total_charge, 3) OVER (PARTITION BY subscriber_key ORDER BY billing_month) as charge_3mo_ago
    FROM {{ ref('stg_billing_monthly') }}
    QUALIFY billing_month = max(billing_month) OVER ()
),
revenue_leaks AS (
    SELECT
        call_sid,
        caller_id,
        duration_seconds,
        charging_key,
        CASE
            WHEN charging_key = 0 AND duration_seconds > 60 THEN 'zero_rating_abuse'
            WHEN charging_key IS NULL AND duration_seconds > 300 THEN 'missing_charge'
            ELSE NULL
        END as leak_type
    FROM {{ ref('stg_cdr') }}
    WHERE charging_key = 0 OR charging_key IS NULL
),
sim_box_detection AS (
    SELECT
        caller_id,
        COUNT(DISTINCT callee_id) as unique_contacts,
        COUNT(*) as total_calls,
        COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT CAST(start_time AS DATE)), 0) as calls_per_day,
        AVG(duration_seconds) as avg_duration,
        COUNT(DISTINCT cell_tower_id) as towers_used
    FROM {{ ref('stg_cdr') }}
    WHERE start_time >= ({{ as_of_date() }} - INTERVAL 7 DAY)
    GROUP BY caller_id
    HAVING COUNT(DISTINCT callee_id) > 20
       AND COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT CAST(start_time AS DATE)), 0) > 50
       AND AVG(duration_seconds) < 30
)

SELECT
    customer_id AS subscriber_key,  -- every signal below is keyed on the shared subscriber key
    call_frequency,
    avg_duration,
    very_short_calls,
    long_calls,
    distinct_towers,
    roaming_frequency,
    total_roaming_cost,
    charge_variance,
    leak_type,
    unique_contacts,
    calls_per_day,

    -- Fraud risk score (0-100)
    GREATEST(0, LEAST(100,
        CASE WHEN very_short_calls > call_frequency * 0.8 THEN 40 ELSE 0 END +
        CASE WHEN distinct_towers > 10 THEN 20 ELSE 0 END +
        CASE WHEN roaming_frequency > 10 THEN 20 ELSE 0 END +
        CASE WHEN charge_variance > 2.0 THEN 20 ELSE 0 END +
        CASE WHEN leak_type IS NOT NULL THEN 30 ELSE 0 END +
        CASE WHEN calls_per_day > 100 THEN 20 ELSE 0 END
    )) as fraud_risk_score,

    -- Fraud type
    CASE
        WHEN leak_type IS NOT NULL THEN leak_type
        WHEN very_short_calls > call_frequency * 0.8 AND distinct_towers < 3 THEN 'sim_box'
        WHEN roaming_frequency > 10 AND total_roaming_cost > 500 THEN 'roaming_fraud'
        WHEN charge_variance > 2.0 THEN 'billing_anomaly'
        WHEN calls_per_day > 100 THEN 'suspected_sim_box'
        ELSE 'low_risk'
    END as fraud_type,

    -- Severity
    CASE
        WHEN GREATEST(0, LEAST(100,
            CASE WHEN very_short_calls > call_frequency * 0.8 THEN 40 ELSE 0 END +
            CASE WHEN distinct_towers > 10 THEN 20 ELSE 0 END +
            CASE WHEN roaming_frequency > 10 THEN 20 ELSE 0 END +
            CASE WHEN charge_variance > 2.0 THEN 20 ELSE 0 END +
            CASE WHEN leak_type IS NOT NULL THEN 30 ELSE 0 END +
            CASE WHEN calls_per_day > 100 THEN 20 ELSE 0 END
        )) > 70 THEN 'critical'
        WHEN GREATEST(0, LEAST(100,
            CASE WHEN very_short_calls > call_frequency * 0.8 THEN 40 ELSE 0 END +
            CASE WHEN distinct_towers > 10 THEN 20 ELSE 0 END +
            CASE WHEN roaming_frequency > 10 THEN 20 ELSE 0 END +
            CASE WHEN charge_variance > 2.0 THEN 20 ELSE 0 END +
            CASE WHEN leak_type IS NOT NULL THEN 30 ELSE 0 END +
            CASE WHEN calls_per_day > 100 THEN 20 ELSE 0 END
        )) > 40 THEN 'high'
        ELSE 'medium'
    END as fraud_severity,

    CURRENT_TIMESTAMP as detection_timestamp
FROM (
    SELECT
        caller_id as customer_id,
        call_frequency,
        avg_duration,
        very_short_calls,
        long_calls,
        distinct_towers,
        NULL as roaming_frequency,
        NULL as total_roaming_cost,
        NULL as charge_variance,
        NULL as leak_type,
        NULL as unique_contacts,
        NULL as calls_per_day
    FROM call_patterns
    WHERE call_frequency > 100

    UNION ALL

    SELECT
        subscriber_key as customer_id,
        NULL as call_frequency,
        NULL as avg_duration,
        NULL as very_short_calls,
        NULL as long_calls,
        NULL as distinct_towers,
        roaming_frequency,
        total_roaming_cost,
        NULL as charge_variance,
        NULL as leak_type,
        NULL as unique_contacts,
        NULL as calls_per_day
    FROM roaming_patterns

    UNION ALL

    SELECT
        subscriber_key as customer_id,
        NULL as call_frequency,
        NULL as avg_duration,
        NULL as very_short_calls,
        NULL as long_calls,
        NULL as distinct_towers,
        NULL as roaming_frequency,
        NULL as total_roaming_cost,
        charge_variance,
        NULL as leak_type,
        NULL as unique_contacts,
        NULL as calls_per_day
    FROM billing_anomalies
    WHERE ABS(charge_variance) > 2.0

    UNION ALL

    SELECT
        caller_id as customer_id,
        NULL as call_frequency,
        NULL as avg_duration,
        NULL as very_short_calls,
        NULL as long_calls,
        NULL as distinct_towers,
        NULL as roaming_frequency,
        NULL as total_roaming_cost,
        NULL as charge_variance,
        leak_type,
        NULL as unique_contacts,
        NULL as calls_per_day
    FROM revenue_leaks
    WHERE leak_type IS NOT NULL

    UNION ALL

    SELECT
        caller_id as customer_id,
        NULL as call_frequency,
        NULL as avg_duration,
        NULL as very_short_calls,
        NULL as long_calls,
        NULL as distinct_towers,
        NULL as roaming_frequency,
        NULL as total_roaming_cost,
        NULL as charge_variance,
        NULL as leak_type,
        unique_contacts,
        calls_per_day
    FROM sim_box_detection
) combined
