{{ config(
    materialized = 'table',
    tags = ['marts', 'marketing', 'propensity']
) }}

-- Cross-Sell and Upsell Propensity Model
-- Predicts customer propensity for different products and services

WITH customer_profile AS (
    SELECT
        customer_id,
        plan_id,
        monthly_charge,
        tenure_days,
        lifetime_value,
        total_calls,
        total_data_mb,
        roaming_sessions,
        total_complaints,
        usage_segment,
        value_segment,
        payment_health,
        churn_risk_score,
        churn_risk_category

    FROM {{ ref('f_customers') }}
),
behavioral_scores AS (
    SELECT
        customer_id,
        -- Data usage propensity
        CASE
            WHEN total_data_mb > 1000 AND usage_segment = 'heavy_user' THEN 0.9
            WHEN total_data_mb > 500 THEN 0.7
            WHEN total_data_mb > 100 THEN 0.5
            ELSE 0.2
        END as data_upsell_propensity,

        -- Roaming propensity
        CASE
            WHEN roaming_sessions > 10 THEN 0.9
            WHEN roaming_sessions > 5 THEN 0.7
            WHEN roaming_sessions > 0 THEN 0.5
            ELSE 0.2
        END as roaming_upsell_propensity,

        -- Voice usage propensity
        CASE
            WHEN total_calls > 500 THEN 0.9
            WHEN total_calls > 200 THEN 0.7
            WHEN total_calls > 100 THEN 0.5
            ELSE 0.2
        END as voice_upsell_propensity,

        -- Upgrade propensity
        CASE
            WHEN lifetime_value > 5000 AND tenure_days > 365 AND payment_health = 'good' THEN 0.9
            WHEN lifetime_value > 2000 AND tenure_days > 180 THEN 0.7
            WHEN lifetime_value > 1000 THEN 0.5
            ELSE 0.3
        END as upgrade_propensity,

        -- Bundle propensity
        CASE
            WHEN total_data_mb > 500 AND roaming_sessions > 0 AND total_calls > 100 THEN 0.9
            WHEN total_data_mb > 200 AND roaming_sessions > 0 THEN 0.7
            WHEN total_data_mb > 100 THEN 0.5
            ELSE 0.3
        END as bundle_propensity,

        -- Churn prevention propensity
        CASE
            WHEN churn_risk_score > 70 AND value_segment = 'high_value' THEN 0.95
            WHEN churn_risk_score > 50 THEN 0.8
            WHEN churn_risk_score > 30 THEN 0.6
            ELSE 0.3
        END as retention_propensity

    FROM customer_profile
),
recommendations AS (
    SELECT
        customer_id,
        -- Primary recommendation
        CASE
            WHEN data_upsell_propensity >= 0.7 AND churn_risk_score < 30 THEN 'data_upgrade'
            WHEN roaming_upsell_propensity >= 0.7 AND churn_risk_score < 30 THEN 'roaming_package'
            WHEN upgrade_propensity >= 0.7 AND churn_risk_score < 30 THEN 'plan_upgrade'
            WHEN bundle_propensity >= 0.7 AND churn_risk_score < 30 THEN 'bundle_offer'
            WHEN retention_propensity >= 0.8 THEN 'retention_offer'
            ELSE 'standard_offer'
        END as primary_recommendation,

        -- Secondary recommendation
        CASE
            WHEN data_upsell_propensity >= 0.7 THEN 'data_add_on'
            WHEN roaming_upsell_propensity >= 0.7 THEN 'roaming_add_on'
            ELSE 'none'
        END as secondary_recommendation,

        -- Priority score (1-10)
        GREATEST(1, LEAST(10,
            CASE WHEN churn_risk_score > 70 THEN 10
                 WHEN churn_risk_score > 50 THEN 8
                 WHEN churn_risk_score > 30 THEN 6
                 ELSE 4 END +
            CASE WHEN lifetime_value > 5000 THEN 3
                 WHEN lifetime_value > 2000 THEN 2
                 ELSE 1 END +
            CASE WHEN tenure_days > 365 THEN 2
                 ELSE 0 END
        )) as priority_score,

        -- Recommended channels
        CASE
            WHEN churn_risk_score > 50 THEN 'phone,sms,push'
            WHEN lifetime_value > 3000 THEN 'email,push'
            ELSE 'email'
        END as recommended_channels,

        -- Product-specific propensities
        data_upsell_propensity,
        roaming_upsell_propensity,
        voice_upsell_propensity,
        upgrade_propensity,
        bundle_propensity,
        retention_propensity

    FROM behavioral_scores
)

SELECT
    customer_id,
    primary_recommendation,
    secondary_recommendation,
    priority_score,
    recommended_channels,
    ROUND(data_upsell_propensity * 100, 1) as data_upsell_probability,
    ROUND(roaming_upsell_propensity * 100, 1) as roaming_upsell_probability,
    ROUND(voice_upsell_propensity * 100, 1) as voice_upsell_probability,
    ROUND(upgrade_propensity * 100, 1) as plan_upgrade_probability,
    ROUND(bundle_propensity * 100, 1) as bundle_propensity_probability,
    ROUND(retention_propensity * 100, 1) as retention_probability,
    CURRENT_TIMESTAMP as model_generated_timestamp
FROM recommendations
ORDER BY priority_score DESC, customer_id
