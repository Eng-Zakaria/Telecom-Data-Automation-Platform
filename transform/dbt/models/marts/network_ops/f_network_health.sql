{{ config(
    materialized = 'table',
    tags = ['marts', 'network_ops', 'health']
) }}

-- Network Health Dashboard
-- Aggregated network performance metrics by region and tower type

WITH tower_health AS (
    SELECT
        k.tower_id,
        d.tower_type,
        d.region,
        d.city,
        k.tower_health_status,
        k.tower_stability,
        k.maintenance_priority,
        k.overall_rsrp,
        k.overall_congestion,
        k.overall_dropped_call_rate,
        k.overall_latency,
        k.overall_handover_success,
        k.congestion_volatility,
        k.drop_rate_volatility
    FROM {{ ref('f_network_kpis') }} k
    -- tower attributes live in the registry, not in the KPI fact
    LEFT JOIN {{ ref('dim_towers') }} d USING (tower_id)
),
regional_summary AS (
    SELECT
        region,
        tower_type,
        COUNT(*) as total_towers,
        SUM(CASE WHEN tower_health_status = 'healthy' THEN 1 ELSE 0 END) as healthy_towers,
        SUM(CASE WHEN tower_health_status = 'degraded' THEN 1 ELSE 0 END) as degraded_towers,
        SUM(CASE WHEN tower_health_status = 'critical' THEN 1 ELSE 0 END) as critical_towers,
        AVG(overall_rsrp) as avg_signal_strength,
        AVG(overall_congestion) as avg_congestion,
        AVG(overall_dropped_call_rate) as avg_drop_rate,
        AVG(overall_latency) as avg_latency,
        AVG(overall_handover_success) as avg_handover_success,
        SUM(CASE WHEN maintenance_priority = 'critical' THEN 1 ELSE 0 END) as critical_maintenance,
        SUM(CASE WHEN maintenance_priority = 'attention' THEN 1 ELSE 0 END) as attention_needed
    FROM tower_health
    GROUP BY region, tower_type
),
city_performance AS (
    SELECT
        city,
        COUNT(*) as tower_count,
        AVG(overall_rsrp) as avg_signal,
        AVG(overall_congestion) as avg_congestion,
        AVG(overall_dropped_call_rate) as avg_drop_rate,
        AVG(overall_latency) as avg_latency,
        SUM(CASE WHEN tower_health_status = 'degraded' THEN 1 ELSE 0 END) as degraded_count,
        SUM(CASE WHEN tower_health_status = 'critical' THEN 1 ELSE 0 END) as critical_count
    FROM tower_health
    GROUP BY city
),
trend_analysis AS (
    SELECT
        tower_id,
        CAST(timestamp AS DATE) as date,
        AVG(congestion_pct) as daily_congestion,
        AVG(dropped_call_rate_pct) as daily_drop_rate,
        AVG(rsrp_dbm) as daily_rsrp
    FROM {{ ref('stg_network_kpi') }}
    WHERE timestamp >= ({{ as_of_date() }} - INTERVAL 30 DAY)
    GROUP BY tower_id, CAST(timestamp AS DATE)
),
tower_trends AS (
    SELECT
        tower_id,
        AVG(daily_congestion) as avg_congestion_30d,
        AVG(daily_drop_rate) as avg_drop_rate_30d,
        AVG(daily_rsrp) as avg_rsrp_30d,
        STDDEV(daily_congestion) as congestion_trend,
        STDDEV(daily_drop_rate) as drop_rate_trend
    FROM trend_analysis
    GROUP BY tower_id
    HAVING STDDEV(daily_congestion) > 5 OR STDDEV(daily_drop_rate) > 1
)

SELECT
    'regional' as snapshot_type,
    region,
    tower_type,
    total_towers,
    healthy_towers,
    degraded_towers,
    critical_towers,
    avg_signal_strength,
    avg_congestion,
    avg_drop_rate,
    avg_latency,
    avg_handover_success,
    critical_maintenance,
    attention_needed,
    NULL as city,
    NULL as tower_count,
    NULL as degraded_count,
    NULL as critical_count,
    NULL as avg_congestion_30d,
    NULL as congestion_trend
FROM regional_summary

UNION ALL

SELECT
    'city' as snapshot_type,
    NULL as region,
    NULL as tower_type,
    NULL as total_towers,
    NULL as healthy_towers,
    NULL as degraded_towers,
    NULL as critical_towers,
    NULL as avg_signal_strength,
    NULL as avg_congestion,
    NULL as avg_drop_rate,
    NULL as avg_latency,
    NULL as avg_handover_success,
    NULL as critical_maintenance,
    NULL as attention_needed,
    city,
    tower_count,
    degraded_count,
    critical_count,
    NULL as avg_congestion_30d,
    NULL as congestion_trend
FROM city_performance

UNION ALL

SELECT
    'trend' as snapshot_type,
    NULL as region,
    NULL as tower_type,
    NULL as total_towers,
    NULL as healthy_towers,
    NULL as degraded_towers,
    NULL as critical_towers,
    NULL as avg_signal_strength,
    NULL as avg_congestion,
    NULL as avg_drop_rate,
    NULL as avg_latency,
    NULL as avg_handover_success,
    NULL as critical_maintenance,
    NULL as attention_needed,
    NULL as city,
    NULL as tower_count,
    NULL as degraded_count,
    NULL as critical_count,
    AVG(avg_congestion_30d) as avg_congestion_30d,
    AVG(congestion_trend) as congestion_trend
FROM tower_trends
GROUP BY tower_id
