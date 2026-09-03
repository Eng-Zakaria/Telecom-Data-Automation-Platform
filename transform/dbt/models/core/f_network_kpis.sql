{{ config(
    materialized = 'table',
    tags = ['core', 'network']
) }}

-- Network KPIs Gold Layer
-- Aggregated per-tower metrics with degradation detection

WITH daily_kpis AS (
    SELECT
        tower_id,
        DATE(timestamp) as date,
        AVG(rsrp_dbm) as avg_rsrp,
        AVG(rsrq_db) as avg_rsrq,
        AVG(sinr_db) as avg_sinr,
        AVG(dropped_call_rate_pct) as avg_dropped_call_rate,
        AVG(congestion_pct) as avg_congestion,
        AVG(latency_ms) as avg_latency,
        AVG(uplink_throughput_mbps) as avg_ul_throughput,
        AVG(downlink_throughput_mbps) as avg_dl_throughput,
        AVG(handover_success_rate_pct) as avg_handover_success,
        AVG(active_users) as avg_active_users,
        SUM(total_calls) as total_calls,
        COUNT(*) as num_measurements
    FROM {{ ref('stg_network_kpi') }}
    WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
    GROUP BY tower_id, DATE(timestamp)
),
tower_stats AS (
    SELECT
        tower_id,
        AVG(avg_rsrp) as overall_rsrp,
        AVG(avg_congestion) as overall_congestion,
        AVG(avg_dropped_call_rate) as overall_dropped_call_rate,
        AVG(avg_latency) as overall_latency,
        AVG(avg_handover_success) as overall_handover_success,
        STDDEV(avg_congestion) as congestion_volatility,
        STDDEV(avg_dropped_call_rate) as drop_rate_volatility,
        COUNT(*) as days_with_data
    FROM daily_kpis
    GROUP BY tower_id
),
degradation_flags AS (
    SELECT
        tower_id,
        CASE
            WHEN overall_congestion > 30 OR overall_dropped_call_rate > 3
            THEN 'degraded'
            WHEN overall_congestion > 20 OR overall_dropped_call_rate > 2
            THEN 'concern'
            ELSE 'healthy'
        END as tower_health_status,
        CASE
            WHEN congestion_volatility > 10 OR drop_rate_volatility > 1
            THEN 'unstable'
            ELSE 'stable'
        END as tower_stability
    FROM tower_stats
)

SELECT
    t.tower_id,
    t.overall_rsrp,
    t.overall_congestion,
    t.overall_dropped_call_rate,
    t.overall_latency,
    t.overall_handover_success,
    t.congestion_volatility,
    t.drop_rate_volatility,
    t.days_with_data,
    d.tower_health_status,
    d.tower_stability,
    CASE
        WHEN d.tower_health_status = 'degraded' AND d.tower_stability = 'unstable' THEN 'critical'
        WHEN d.tower_health_status = 'degraded' OR d.tower_stability = 'unstable' THEN 'attention'
        ELSE 'normal'
    END as maintenance_priority,
    CURRENT_TIMESTAMP as gold_ingestion_timestamp
FROM tower_stats t
LEFT JOIN degradation_flags d ON t.tower_id = d.tower_id
