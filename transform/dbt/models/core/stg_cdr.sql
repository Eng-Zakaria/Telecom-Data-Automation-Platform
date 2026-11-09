{{ config(
    materialized = 'view',
    tags = ['staging', 'cdr']
) }}

-- Staging layer for CDR data
-- Cleans and standardizes raw CDR records

SELECT
    call_sid,
    caller_id,
    caller_id AS subscriber_key,
    callee_id,
    start_time,
    duration_seconds,
    cell_tower_id,
    tower_type,
    call_type,
    direction,
    roaming_flag,
    data_volume_mb,
    charging_key,
    error_code,
    geographic_lat,
    geographic_lon,
    network_type,
    signal_strength_dbm,
    CAST(start_time AS DATE) as call_date,
    HOUR(start_time) as call_hour,
    DAYOFWEEK(start_time) as call_day_of_week,
    CASE
        WHEN duration_seconds < 10 THEN 'very_short'
        WHEN duration_seconds < 60 THEN 'short'
        WHEN duration_seconds < 300 THEN 'medium'
        WHEN duration_seconds < 1800 THEN 'long'
        ELSE 'very_long'
    END as call_duration_category,
    CASE
        WHEN signal_strength_dbm > -80 THEN 'excellent'
        WHEN signal_strength_dbm > -90 THEN 'good'
        WHEN signal_strength_dbm > -100 THEN 'fair'
        ELSE 'poor'
    END as signal_quality_category,
    CASE
        WHEN roaming_flag AND network_type = '5G' THEN '5g_roaming'
        WHEN roaming_flag THEN 'roaming'
        WHEN network_type = '5G' THEN '5g_domestic'
        WHEN network_type = '4G' THEN '4g_domestic'
        ELSE 'other'
    END as network_category,
    CURRENT_TIMESTAMP as staging_ingestion_timestamp
FROM {{ source('silver', 'cdr') }}
WHERE call_sid IS NOT NULL
