{{ config(
    materialized = 'table',
    tags = ['marts', 'roaming', 'analytics']
) }}

-- Roaming Analytics and Settlement Tracking
-- Tracks roaming revenue, costs, and partner settlements

WITH session_analysis AS (
    SELECT
        r.partner_id,
        p.name as partner_name,
        p.country_code,
        p.agreement_type,
        COUNT(*) as total_sessions,
        SUM(CASE WHEN r.roaming_type = 'voice' THEN 1 ELSE 0 END) as voice_sessions,
        SUM(CASE WHEN r.roaming_type = 'sms' THEN 1 ELSE 0 END) as sms_sessions,
        SUM(CASE WHEN r.roaming_type = 'data' THEN 1 ELSE 0 END) as data_sessions,
        SUM(r.voice_minutes) as total_voice_minutes,
        SUM(r.data_mb) as total_data_mb,
        SUM(r.settlement_amount) as total_settlement_cost,
        AVG(r.duration_seconds) as avg_session_duration,
        MAX(r.start_time) as last_roaming_date
    FROM {{ ref('stg_roaming_sessions') }} r
    JOIN {{ ref('dim_roaming_partners') }} p ON r.partner_id = p.partner_id
    WHERE r.start_time >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
    GROUP BY r.partner_id, p.name, p.country_code, p.agreement_type
),
revenue_analysis AS (
    SELECT
        partner_id,
        SUM(settlement_amount * 3) as estimated_revenue,
        SUM(settlement_amount) as total_cost,
        SUM(settlement_amount * 2) as net_revenue,
        AVG(settlement_amount * 3.0 / NULLIF(settlement_amount, 0)) as avg_markup
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    GROUP BY partner_id
),
anomaly_detection AS (
    SELECT
        customer_id,
        COUNT(*) as session_count,
        SUM(settlement_amount) as total_cost,
        COUNT(DISTINCT partner_id) as distinct_partners,
        AVG(duration_seconds) as avg_duration,
        MAX(start_time) as last_session
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
    GROUP BY customer_id
    HAVING COUNT(*) > 10 OR SUM(settlement_amount) > 1000
),
settlement_tracking AS (
    SELECT
        partner_id,
        settlement_period,
        total_voice_minutes,
        total_sms,
        total_data_mb,
        total_revenue,
        total_settlement_cost,
        net_revenue,
        reconciliation_status,
        CASE
            WHEN reconciliation_status = 'discrepancy' THEN 'needs_review'
            WHEN reconciliation_status = 'pending' THEN 'awaiting'
            ELSE 'settled'
        END as settlement_status
    FROM {{ ref('stg_roaming_settlements') }}
    WHERE settlement_period >= DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 3 MONTH), '%Y-%m')
)

SELECT
    'partner_performance' as analysis_type,
    s.partner_id,
    s.partner_name,
    s.country_code,
    s.agreement_type,
    s.total_sessions,
    s.voice_sessions,
    s.sms_sessions,
    s.data_sessions,
    s.total_voice_minutes,
    s.total_data_mb,
    s.total_settlement_cost,
    r.estimated_revenue,
    r.net_revenue,
    r.avg_markup,
    s.last_roaming_date,
    NULL as settlement_period,
    NULL as total_revenue_settled,
    NULL as reconciliation_status
FROM session_analysis s
LEFT JOIN revenue_analysis r ON s.partner_id = r.partner_id

UNION ALL

SELECT
    'anomaly_detection' as analysis_type,
    a.customer_id as partner_id,
    NULL as partner_name,
    NULL as country_code,
    NULL as agreement_type,
    a.session_count as total_sessions,
    NULL as voice_sessions,
    NULL as sms_sessions,
    NULL as data_sessions,
    NULL as total_voice_minutes,
    NULL as total_data_mb,
    a.total_cost as total_settlement_cost,
    NULL as estimated_revenue,
    NULL as net_revenue,
    NULL as avg_markup,
    a.last_session,
    NULL as settlement_period,
    NULL as total_revenue_settled,
    NULL as reconciliation_status
FROM anomaly_detection a

UNION ALL

SELECT
    'settlement_status' as analysis_type,
    st.partner_id,
    NULL as partner_name,
    NULL as country_code,
    NULL as agreement_type,
    NULL as total_sessions,
    NULL as voice_sessions,
    NULL as sms_sessions,
    NULL as data_sessions,
    NULL as total_voice_minutes,
    NULL as total_data_mb,
    st.total_settlement_cost,
    st.total_revenue as estimated_revenue,
    st.net_revenue,
    NULL as avg_markup,
    NULL as last_roaming_date,
    st.settlement_period,
    st.total_revenue,
    st.reconciliation_status
FROM settlement_tracking st
