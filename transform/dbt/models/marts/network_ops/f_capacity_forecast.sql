{{ config(
    materialized = 'table',
    tags = ['marts', 'network_ops', 'forecasting']
) }}

-- Capacity and Congestion Forecasting
-- Predicts future capacity needs based on trends

WITH historical_usage AS (
    SELECT
        tower_id,
        CAST(timestamp AS DATE) as date,
        AVG(active_users) as avg_active_users,
        AVG(congestion_pct) as avg_congestion,
        SUM(total_calls) as total_calls,
        AVG(downlink_throughput_mbps) as avg_throughput
    FROM {{ ref('stg_network_kpi') }}
    WHERE timestamp >= ({{ as_of_date() }} - INTERVAL 90 DAY)
    GROUP BY tower_id, CAST(timestamp AS DATE)
),
tower_trends AS (
    SELECT
        tower_id,
        AVG(avg_active_users) as current_avg_users,
        AVG(avg_congestion) as current_avg_congestion,
        AVG(avg_throughput) as current_avg_throughput,
        -- Trend calculation (simple linear regression slope)
        (MAX(avg_active_users) - MIN(avg_active_users)) / NULLIF(COUNT(DISTINCT date), 0) as users_trend,
        (MAX(avg_congestion) - MIN(avg_congestion)) / NULLIF(COUNT(DISTINCT date), 0) as congestion_trend
    FROM historical_usage
    GROUP BY tower_id
),
forecast AS (
    SELECT
        tower_id,
        current_avg_users,
        current_avg_congestion,
        current_avg_throughput,
        users_trend,
        congestion_trend,
        -- 7-day forecast
        current_avg_users + (users_trend * 7) as forecasted_users_7d,
        current_avg_congestion + (congestion_trend * 7) as forecasted_congestion_7d,
        -- 30-day forecast
        current_avg_users + (users_trend * 30) as forecasted_users_30d,
        current_avg_congestion + (congestion_trend * 30) as forecasted_congestion_30d,
        -- Capacity alert flags
        CASE
            WHEN current_avg_congestion > 50 OR forecasted_congestion_7d > 60 THEN 'immediate_action'
            WHEN current_avg_congestion > 30 OR forecasted_congestion_7d > 40 THEN 'planned_upgrade'
            WHEN forecasted_congestion_30d > 35 THEN 'monitor'
            ELSE 'normal'
        END as capacity_action_required,
        -- Suggested capacity increase
        GREATEST(0, current_avg_congestion - 30) as suggested_capacity_increase_pct
    FROM tower_trends
    WHERE users_trend IS NOT NULL AND congestion_trend IS NOT NULL
)

SELECT * FROM forecast
ORDER BY forecasted_congestion_7d DESC
