{{ config(
    materialized = 'table',
    tags = ['marts', 'customer_care', 'routing']
) }}

-- Ticket Routing and Resolution Analysis
-- Optimizes ticket routing and measures first-contact resolution

WITH ticket_metrics AS (
    SELECT
        complaint_id,
        customer_id_hash,
        source,
        platform,
        language,
        category,
        issue_type,
        sentiment,
        severity,
        complaint_priority,
        posted_date,
        resolved,
        resolution_time_days,
        upvotes,

        -- Routing classification
        CASE
            WHEN severity IN ('critical', 'high') AND sentiment = 'negative' THEN 'urgent'
            WHEN category = 'network' AND sentiment = 'negative' THEN 'technical'
            WHEN category = 'billing' AND sentiment = 'negative' THEN 'billing'
            WHEN category = 'customer_service' THEN 'service'
            WHEN category = 'roaming' THEN 'roaming'
            ELSE 'general'
        END as routed_queue,

        -- Estimated resolution time
        CASE
            WHEN severity = 'critical' THEN 24
            WHEN severity = 'high' THEN 48
            WHEN severity = 'medium' THEN 72
            ELSE 96
        END as estimated_resolution_hours,

        -- First contact resolution probability
        CASE
            WHEN issue_type IN ('billing_issue', 'service_issue')
                 AND severity IN ('low', 'medium')
                 AND upvotes < 5 THEN 'high'
            WHEN issue_type = 'network_issue' AND severity = 'low' THEN 'medium'
            ELSE 'low'
        END as fcr_probability

    FROM {{ ref('stg_complaints') }}
    WHERE posted_date >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
),
queue_performance AS (
    SELECT
        routed_queue,
        COUNT(*) as total_tickets,
        SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved_tickets,
        AVG(resolution_time_days) as avg_resolution_days,
        MIN(resolution_time_days) as min_resolution_days,
        MAX(resolution_time_days) as max_resolution_days,
        AVG(upvotes) as avg_engagement,
        SUM(CASE WHEN fcr_probability = 'high' THEN 1 ELSE 0 END) as high_fcr_count
    FROM ticket_metrics
    GROUP BY routed_queue
),
agent_load AS (
    SELECT
        routed_queue,
        COUNT(*) as tickets_assigned,
        SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as tickets_resolved,
        AVG(resolution_time_days) as avg_handling_time,
        COUNT(*) * 1.0 / NULLIF(AVG(resolution_time_days), 0) as throughput_rate
    FROM ticket_metrics
    GROUP BY routed_queue
),
sla_compliance AS (
    SELECT
        routed_queue,
        SUM(CASE WHEN resolution_time_days <= estimated_resolution_hours / 24 THEN 1 ELSE 0 END) as sla_met,
        COUNT(*) as total_tickets,
        SUM(CASE WHEN resolution_time_days <= estimated_resolution_hours / 24 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as sla_compliance_rate
    FROM ticket_metrics
    WHERE resolved = true
    GROUP BY routed_queue
)

SELECT
    'queue_performance' as analysis_type,
    qp.routed_queue,
    qp.total_tickets,
    qp.resolved_tickets,
    qp.avg_resolution_days,
    qp.min_resolution_days,
    qp.max_resolution_days,
    qp.avg_engagement,
    qp.high_fcr_count,
    NULL as tickets_assigned,
    NULL as tickets_resolved,
    NULL as avg_handling_time,
    NULL as throughput_rate,
    NULL as sla_met,
    NULL as total_tickets_sla,
    NULL as sla_compliance_rate
FROM queue_performance qp

UNION ALL

SELECT
    'agent_load' as analysis_type,
    al.routed_queue,
    NULL as total_tickets,
    NULL as resolved_tickets,
    NULL as avg_resolution_days,
    NULL as min_resolution_days,
    NULL as max_resolution_days,
    NULL as avg_engagement,
    NULL as high_fcr_count,
    al.tickets_assigned,
    al.tickets_resolved,
    al.avg_handling_time,
    al.throughput_rate,
    NULL as sla_met,
    NULL as total_tickets_sla,
    NULL as sla_compliance_rate
FROM agent_load al

UNION ALL

SELECT
    'sla_compliance' as analysis_type,
    sla.routed_queue,
    NULL as total_tickets,
    NULL as resolved_tickets,
    NULL as avg_resolution_days,
    NULL as min_resolution_days,
    NULL as max_resolution_days,
    NULL as avg_engagement,
    NULL as high_fcr_count,
    NULL as tickets_assigned,
    NULL as tickets_resolved,
    NULL as avg_handling_time,
    NULL as throughput_rate,
    sla.sla_met,
    sla.total_tickets as total_tickets_sla,
    sla.sla_compliance_rate
FROM sla_compliance sla
