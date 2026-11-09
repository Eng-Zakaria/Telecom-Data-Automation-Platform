{{ config(
    materialized = 'table',
    tags = ['core', 'dimension']
) }}

-- Plan dimension: the tariff catalogue (previously derived from billing columns that
-- do not exist; now read from the plans feed).

SELECT
    plan_id,
    name,
    name                                         AS plan_name,
    type,
    type                                         AS plan_type,
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
    END AS plan_category,
    CASE
        WHEN monthly_fee < 50 THEN 'budget'
        WHEN monthly_fee < 150 THEN 'standard'
        WHEN monthly_fee < 300 THEN 'premium'
        ELSE 'enterprise'
    END AS price_tier,
    CURRENT_TIMESTAMP AS dim_updated_timestamp
FROM {{ source('silver', 'plans') }}
