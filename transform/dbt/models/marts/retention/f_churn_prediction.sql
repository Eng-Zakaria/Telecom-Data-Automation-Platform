{{ config(
    materialized = 'table',
    tags = ['marts', 'retention', 'churn']
) }}

-- Rule-based churn risk score (0-100) per subscriber: transparent, auditable features that
-- a retention team can act on today and that seed the ML churn model in ml/churn_model.
-- features -> score -> band: each step is computed once (the score used to be repeated
-- three times inline, and referenced an alias of its own SELECT).

WITH features AS (
    SELECT
        c.customer_id,
        c.subscriber_key,
        c.hashed_id,
        c.plan_id,
        c.monthly_charge,
        c.tenure_days,
        c.lifetime_value,
        c.payment_status,
        coalesce(c.total_calls, 0)       AS total_calls,
        coalesce(c.total_data_mb, 0)     AS total_data_mb,
        c.avg_signal_strength,
        coalesce(c.total_complaints, 0)  AS total_complaints,
        coalesce(c.resolved_complaints, 0) AS resolved_complaints,
        coalesce(c.roaming_sessions, 0)  AS roaming_sessions,
        c.tenure_segment,
        c.value_segment,
        c.payment_health,
        c.usage_segment,
        CASE WHEN c.total_complaints > 0
             THEN c.resolved_complaints::DOUBLE / c.total_complaints ELSE 1.0 END  AS complaint_resolution_rate,
        CASE WHEN c.tenure_days > 0
             THEN coalesce(c.total_calls, 0)::DOUBLE / c.tenure_days ELSE 0 END    AS call_frequency,
        CASE WHEN c.total_calls > 0
             THEN coalesce(c.roaming_sessions, 0)::DOUBLE / c.total_calls ELSE 0 END AS roaming_ratio,
        CASE WHEN c.lifetime_value > 0
             THEN c.monthly_charge::DOUBLE / c.lifetime_value ELSE 0 END           AS charge_to_value_ratio,
        CASE
            WHEN c.avg_signal_strength < -100 THEN 'poor_signal'
            WHEN c.avg_signal_strength < -90 THEN 'weak_signal'
            ELSE 'good_signal'
        END AS signal_quality_flag
    FROM {{ ref('f_customers') }} c
),

scored AS (
    SELECT
        *,
        greatest(0, least(100,
              CASE WHEN payment_health = 'at_risk' THEN 30 ELSE 0 END
            + CASE WHEN total_complaints > 3 THEN 25 ELSE 0 END
            + CASE WHEN tenure_days < 90 THEN 20 ELSE 0 END
            + CASE WHEN avg_signal_strength < -95 THEN 15 ELSE 0 END
            + CASE WHEN roaming_ratio > 0.3 THEN 10 ELSE 0 END
            + CASE WHEN usage_segment = 'light_user' AND tenure_days > 180 THEN 10 ELSE 0 END
        )) AS churn_risk_score
    FROM features
)

SELECT
    *,
    CASE
        WHEN churn_risk_score > 70 THEN 'high'
        WHEN churn_risk_score > 40 THEN 'medium'
        ELSE 'low'
    END AS churn_risk_category,
    CURRENT_TIMESTAMP AS model_generated_timestamp
FROM scored
