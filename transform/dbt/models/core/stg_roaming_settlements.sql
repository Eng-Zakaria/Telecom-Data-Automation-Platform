{{ config(materialized='view', tags=['staging', 'roaming']) }}

-- Monthly settlement statements per partner (TAP/RAP reconciliation).
SELECT
    partner_id,
    settlement_period,
    CAST(strptime(settlement_period || '-01', '%Y-%m-%d') AS DATE) AS settlement_month_start,
    total_voice_minutes,
    total_sms,
    total_data_mb,
    total_revenue,
    total_settlement_cost,
    net_revenue,
    reconciliation_status
FROM {{ source('silver', 'roaming_settlements') }}
