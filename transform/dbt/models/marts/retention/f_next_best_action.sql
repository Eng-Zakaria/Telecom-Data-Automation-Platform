{{ config(
    materialized = 'table',
    tags = ['marts', 'retention', 'nba']
) }}

-- Next Best Action Model
-- Recommends actions for customer retention and upsell

WITH churn_risk AS (
    SELECT
        customer_id,
        churn_risk_score,
        churn_risk_category,
        tenure_days,
        lifetime_value,
        payment_health,
        complaint_resolution_rate,
        signal_quality_flag,
        usage_segment
    FROM {{ ref('f_churn_prediction') }}
),
network_quality AS (
    SELECT
        tower_id,
        tower_health_status,
        maintenance_priority
    FROM {{ ref('f_network_kpis') }}
    WHERE tower_health_status IN ('degraded', 'critical')
),
customer_network AS (
    SELECT DISTINCT
        c.customer_id,
        c.last_activity,
        t.tower_id,
        t.tower_health_status
    FROM {{ ref('f_customers') }} c
    LEFT JOIN {{ ref('dim_towers') }} t ON c.customer_id = t.tower_id
),
recommendations AS (
    SELECT
        cr.customer_id,
        cr.churn_risk_score,
        cr.churn_risk_category,

        -- Primary recommendation
        CASE
            WHEN cr.churn_risk_category = 'high' AND cr.payment_health = 'at_risk' THEN 'payment_assistance'
            WHEN cr.churn_risk_category = 'high' AND cr.complaint_resolution_rate < 0.5 THEN 'proactive_support'
            WHEN cr.churn_risk_category = 'high' AND cr.signal_quality_flag = 'poor_signal' THEN 'network_improvement'
            WHEN cr.churn_risk_category = 'high' THEN 'retention_offer'
            WHEN cr.churn_risk_category = 'medium' AND cr.tenure_days < 180 THEN 'engagement_campaign'
            WHEN cr.churn_risk_category = 'medium' THEN 'loyalty_program'
            ELSE 'generic_retention'
        END as primary_recommendation,

        -- Secondary recommendation
        CASE
            WHEN cr.lifetime_value > 5000 AND cr.usage_segment = 'light_user' THEN 'upsell_premium'
            WHEN cr.lifetime_value > 2000 AND cr.usage_segment = 'regular_user' THEN 'upsell_data'
            WHEN cr.lifetime_value < 2000 AND cr.tenure_days > 365 THEN 'cross_sell'
            ELSE 'retain_current'
        END as secondary_recommendation,

        -- Priority score (1-5)
        CASE
            WHEN cr.churn_risk_score > 70 THEN 5
            WHEN cr.churn_risk_score > 50 THEN 4
            WHEN cr.churn_risk_score > 30 THEN 3
            WHEN cr.churn_risk_score > 15 THEN 2
            ELSE 1
        END as priority_level,

        -- Recommended channels
        CASE
            WHEN cr.churn_risk_category = 'high' THEN 'phone,sms,push'
            WHEN cr.churn_risk_category = 'medium' THEN 'sms,push,email'
            ELSE 'email,push'
        END as recommended_channels,

        CURRENT_TIMESTAMP as generated_timestamp
    FROM churn_risk cr
)

SELECT * FROM recommendations
