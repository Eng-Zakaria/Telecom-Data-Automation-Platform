{{ config(
    materialized = 'table',
    tags = ['marts', 'retention', 'segmentation']
) }}

-- Customer Segmentation Model
-- Clusters customers based on usage patterns and behavior

WITH customer_metrics AS (
    SELECT
        customer_id,
        total_calls,
        voice_calls,
        sms_count,
        data_sessions,
        total_call_duration_sec,
        total_data_mb,
        roaming_sessions,
        total_complaints,
        lifetime_value,
        tenure_days,
        monthly_charge,
        payment_status
    FROM {{ ref('f_customers') }}
),
normalized_metrics AS (
    SELECT
        customer_id,
        -- Usage intensity score (0-100)
        LEAST(100, (total_calls / NULLIF(MAX(total_calls) OVER (), 0)) * 100) as usage_intensity,

        -- Data consumption score (0-100)
        LEAST(100, (total_data_mb / NULLIF(MAX(total_data_mb) OVER (), 0)) * 100) as data_consumption,

        -- Loyalty score (0-100)
        LEAST(100, (tenure_days / 730.0) * 100) as loyalty_score,

        -- Value score (0-100)
        LEAST(100, (lifetime_value / NULLIF(MAX(lifetime_value) OVER (), 0)) * 100) as value_score,

        -- Risk score (0-100)
        GREATEST(0,
            CASE WHEN payment_status = 'defaulted' THEN 100
                 WHEN payment_status = 'overdue' THEN 70
                 ELSE 0 END +
            CASE WHEN total_complaints > 3 THEN 30
                 WHEN total_complaints > 1 THEN 15
                 ELSE 0 END
        ) as risk_score
    FROM customer_metrics
)

SELECT
    cm.customer_id,
    cm.total_calls,
    cm.voice_calls,
    cm.sms_count,
    cm.data_sessions,
    cm.total_data_mb,
    cm.roaming_sessions,
    cm.total_complaints,
    cm.lifetime_value,
    cm.tenure_days,
    cm.monthly_charge,
    cm.payment_status,

    nm.usage_intensity,
    nm.data_consumption,
    nm.loyalty_score,
    nm.value_score,
    nm.risk_score,

    -- Primary segment
    CASE
        WHEN nm.value_score > 70 AND nm.risk_score < 30 THEN 'high_value_loyal'
        WHEN nm.value_score > 70 AND nm.risk_score >= 30 THEN 'high_value_risky'
        WHEN nm.usage_intensity > 70 AND nm.data_consumption > 70 THEN 'heavy_data_user'
        WHEN nm.usage_intensity > 70 THEN 'heavy_voice_user'
        WHEN nm.loyalty_score > 70 THEN 'loyal_longterm'
        WHEN nm.risk_score > 50 THEN 'at_risk'
        WHEN nm.value_score < 30 AND nm.usage_intensity < 30 THEN 'low_value_inactive'
        ELSE 'standard'
    END as primary_segment,

    -- Secondary segment
    CASE
        WHEN nm.data_consumption > 70 THEN 'data_heavy'
        WHEN nm.usage_intensity > 70 AND nm.data_consumption < 30 THEN 'voice_heavy'
        WHEN nm.roaming_sessions > 10 THEN 'roaming_heavy'
        ELSE 'balanced'
    END as secondary_segment,

    -- Recommended action
    CASE
        WHEN nm.value_score > 70 AND nm.risk_score < 30 THEN 'maintain_relationship'
        WHEN nm.value_score > 70 AND nm.risk_score >= 30 THEN 'retention_intervention'
        WHEN nm.usage_intensity > 70 AND nm.data_consumption < 30 THEN 'upsell_data'
        WHEN nm.data_consumption > 70 AND nm.usage_intensity < 30 THEN 'upsell_voice'
        WHEN nm.loyalty_score < 30 THEN 'engagement_program'
        WHEN nm.risk_score > 50 THEN 'risk_mitigation'
        ELSE 'standard_care'
    END as recommended_action,

    CURRENT_TIMESTAMP as segmentation_timestamp
FROM customer_metrics cm
JOIN normalized_metrics nm ON cm.customer_id = nm.customer_id
