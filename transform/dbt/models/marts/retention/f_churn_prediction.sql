{{ config(
    materialized = 'table',
    tags = ['marts', 'retention', 'churn']
) }}

-- Churn Prediction Model
-- Predicts customer churn probability using multiple features

WITH customer_features AS (
    SELECT
        c.customer_id,
        c.hashed_id,
        c.plan_id,
        c.monthly_charge,
        c.tenure_days,
        c.lifetime_value,
        c.payment_status,
        c.total_calls,
        c.total_data_mb,
        c.avg_signal_strength,
        c.total_complaints,
        c.resolved_complaints,
        c.roaming_sessions,
        c.tenure_segment,
        c.value_segment,
        c.payment_health,
        c.usage_segment,

        -- Derived features
        CASE
            WHEN c.total_complaints > 0
            THEN CAST(c.resolved_complaints AS FLOAT) / c.total_complaints
            ELSE 1.0
        END as complaint_resolution_rate,

        CASE
            WHEN c.tenure_days > 0
            THEN CAST(c.total_calls AS FLOAT) / c.tenure_days
            ELSE 0
        END as call_frequency,

        CASE
            WHEN c.total_calls > 0
            THEN CAST(c.roaming_sessions AS FLOAT) / c.total_calls
            ELSE 0
        END as roaming_ratio,

        CASE
            WHEN c.lifetime_value > 0
            THEN CAST(c.monthly_charge AS FLOAT) / c.lifetime_value
            ELSE 0
        END as charge_to_value_ratio,

        -- Network quality flags
        CASE
            WHEN c.avg_signal_strength < -100 THEN 'poor_signal'
            WHEN c.avg_signal_strength < -90 THEN 'weak_signal'
            ELSE 'good_signal'
        END as signal_quality_flag,

        -- Churn risk score (0-100)
        GREATEST(0, LEAST(100,
            CASE WHEN c.payment_health = 'at_risk' THEN 30 ELSE 0 END +
            CASE WHEN c.total_complaints > 3 THEN 25 ELSE 0 END +
            CASE WHEN c.tenure_days < 90 THEN 20 ELSE 0 END +
            CASE WHEN c.avg_signal_strength < -95 THEN 15 ELSE 0 END +
            CASE WHEN c.roaming_ratio > 0.3 THEN 10 ELSE 0 END +
            CASE WHEN c.usage_segment = 'light_user' AND c.tenure_days > 180 THEN 10 ELSE 0 END
        )) as churn_risk_score,

        -- Churn risk category
        CASE
            WHEN GREATEST(0, LEAST(100,
                CASE WHEN c.payment_health = 'at_risk' THEN 30 ELSE 0 END +
                CASE WHEN c.total_complaints > 3 THEN 25 ELSE 0 END +
                CASE WHEN c.tenure_days < 90 THEN 20 ELSE 0 END +
                CASE WHEN c.avg_signal_strength < -95 THEN 15 ELSE 0 END +
                CASE WHEN c.roaming_ratio > 0.3 THEN 10 ELSE 0 END +
                CASE WHEN c.usage_segment = 'light_user' AND c.tenure_days > 180 THEN 10 ELSE 0 END
            )) > 70 THEN 'high'
            WHEN GREATEST(0, LEAST(100,
                CASE WHEN c.payment_health = 'at_risk' THEN 30 ELSE 0 END +
                CASE WHEN c.total_complaints > 3 THEN 25 ELSE 0 END +
                CASE WHEN c.tenure_days < 90 THEN 20 ELSE 0 END +
                CASE WHEN c.avg_signal_strength < -95 THEN 15 ELSE 0 END +
                CASE WHEN c.roaming_ratio > 0.3 THEN 10 ELSE 0 END +
                CASE WHEN c.usage_segment = 'light_user' AND c.tenure_days > 180 THEN 10 ELSE 0 END
            )) > 40 THEN 'medium'
            ELSE 'low'
        END as churn_risk_category,

        CURRENT_TIMESTAMP as model_generated_timestamp
    FROM {{ ref('f_customers') }} c
)

SELECT * FROM customer_features
