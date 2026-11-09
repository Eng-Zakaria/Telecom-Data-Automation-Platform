{{ config(
    materialized = 'view',
    tags = ['staging', 'roaming']
) }}

-- Staging layer for Roaming data
-- Cleans and standardizes roaming session records

SELECT
    session_id,
    customer_id,
    {{ subscriber_key('customer_id') }} AS subscriber_key,
    partner_id,
    start_time,
    end_time,
    duration_seconds,
    voice_minutes,
    sms_count,
    data_mb,
    roaming_type,
    charging_key,
    settlement_amount,
    CAST(start_time AS DATE) as roaming_date,
    HOUR(start_time) as roaming_hour,
    CASE
        WHEN roaming_type = 'voice' THEN 'voice_call'
        WHEN roaming_type = 'sms' THEN 'sms_message'
        ELSE 'data_session'
    END as session_category,
    CASE
        WHEN settlement_amount > 100 THEN 'high_cost'
        WHEN settlement_amount > 50 THEN 'medium_cost'
        ELSE 'low_cost'
    END as cost_category,
    CASE
        WHEN voice_minutes > 30 OR data_mb > 100 THEN 'heavy_usage'
        WHEN voice_minutes > 10 OR data_mb > 50 THEN 'moderate_usage'
        ELSE 'light_usage'
    END as usage_category,
    CURRENT_TIMESTAMP as staging_ingestion_timestamp
FROM {{ source('silver', 'roaming_sessions') }}
WHERE session_id IS NOT NULL
