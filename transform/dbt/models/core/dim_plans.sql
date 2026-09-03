{{ config(
    materialized = 'table',
    tags = ['core', 'dimension']
) }}

-- Plan Dimension Table
-- Master data for all telecom plans

SELECT
    plan_id,
    name,
    type as plan_type,
    monthly_fee,
    included_minutes,
    included_sms,
    included_data_gb,
    roaming_enabled,
    features,
    CASE
        WHEN type = 'prepaid' THEN 'pay_as_you_go'
        WHEN type = 'postpaid' THEN 'contract'
        WHEN type = 'enterprise' THEN 'business'
        ELSE 'other'
    END as plan_category,
    CASE
        WHEN monthly_fee < 50 THEN 'budget'
        WHEN monthly_fee < 150 THEN 'standard'
        WHEN monthly_fee < 300 THEN 'premium'
        ELSE 'enterprise'
    END as price_tier,
    CURRENT_TIMESTAMP as dim_updated_timestamp
FROM {{ ref('stg_billing') }}
WHERE plan_id IS NOT NULL
GROUP BY plan_id, name, type, monthly_fee, included_minutes, included_sms, included_data_gb, roaming_enabled, features
