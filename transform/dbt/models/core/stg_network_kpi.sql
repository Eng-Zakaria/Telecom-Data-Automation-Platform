{{ config(
    materialized = 'view',
    tags = ['staging', 'network']
) }}

-- Staging layer for Network KPI data
-- Cleans and standardizes tower metrics

SELECT
    tower_id,
    timestamp,
    rsrp_dbm,
    rsrq_db,
    sinr_db,
    dropped_call_rate_pct,
    congestion_pct,
    latency_ms,
    uplink_throughput_mbps,
    downlink_throughput_mbps,
    handover_success_rate_pct,
    active_users,
    total_calls,
    DATE(timestamp) as kpi_date,
    HOUR(timestamp) as kpi_hour,
    DAYOFWEEK(timestamp) as kpi_day_of_week,
    CASE
        WHEN rsrp_dbm > -85 THEN 'excellent'
        WHEN rsrp_dbm > -95 THEN 'good'
        WHEN rsrp_dbm > -105 THEN 'fair'
        ELSE 'poor'
    END as signal_quality_category,
    CASE
        WHEN congestion_pct > 50 THEN 'congested'
        WHEN congestion_pct > 30 THEN 'busy'
        WHEN congestion_pct > 15 THEN 'moderate'
        ELSE 'normal'
    END as congestion_category,
    CASE
        WHEN dropped_call_rate_pct > 5 THEN 'high_drop'
        WHEN dropped_call_rate_pct > 2 THEN 'elevated_drop'
        ELSE 'normal_drop'
    END as drop_rate_category,
    CURRENT_TIMESTAMP as staging_ingestion_timestamp
FROM {{ source('bronze', 'network_kpi_raw') }}
WHERE tower_id IS NOT NULL
