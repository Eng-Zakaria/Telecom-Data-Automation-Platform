{{ config(
    materialized = 'table',
    tags = ['marts', 'finance', 'executive']
) }}

-- Executive KPI Dashboard
-- Unified view of key metrics across all domains

WITH customer_metrics AS (
    SELECT
        COUNT(DISTINCT customer_id) as total_customers,
        COUNT(DISTINCT CASE WHEN tenure_days < 90 THEN customer_id END) as new_customers,
        COUNT(DISTINCT CASE WHEN churn_risk_category = 'high' THEN customer_id END) as high_churn_risk,
        COUNT(DISTINCT CASE WHEN payment_health = 'at_risk' THEN customer_id END) as payment_at_risk,
        AVG(lifetime_value) as avg_customer_lifetime_value,
        SUM(CASE WHEN payment_status = 'paid' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as payment_health_rate
    FROM {{ ref('f_customers') }}
),
financial_metrics AS (
    SELECT
        SUM(total_revenue) as total_monthly_revenue,
        AVG(arpu) as avg_arpu,
        SUM(base_revenue) as base_revenue,
        SUM(usage_revenue) as usage_revenue,
        COUNT(DISTINCT customer_id) as paying_customers,
        AVG(total_charge) as avg_bill
    FROM {{ ref('stg_billing_monthly') }}
    WHERE billing_month = DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH), '%Y-%m')
),
network_metrics AS (
    SELECT
        COUNT(*) as total_towers,
        SUM(CASE WHEN tower_health_status = 'healthy' THEN 1 ELSE 0 END) as healthy_towers,
        SUM(CASE WHEN tower_health_status = 'degraded' THEN 1 ELSE 0 END) as degraded_towers,
        SUM(CASE WHEN tower_health_status = 'critical' THEN 1 ELSE 0 END) as critical_towers,
        AVG(overall_congestion) as avg_congestion,
        AVG(overall_dropped_call_rate) as avg_drop_rate,
        AVG(overall_handover_success) as avg_handover_success
    FROM {{ ref('f_network_kpis') }}
),
fraud_metrics AS (
    SELECT
        COUNT(*) as fraud_cases_detected,
        SUM(CASE WHEN fraud_severity = 'critical' THEN 1 ELSE 0 END) as critical_fraud,
        SUM(CASE WHEN fraud_severity = 'high' THEN 1 ELSE 0 END) as high_fraud,
        SUM(CASE WHEN fraud_type = 'sim_box' THEN 1 ELSE 0 END) as sim_box_cases,
        SUM(CASE WHEN fraud_type = 'roaming_fraud' THEN 1 ELSE 0 END) as roaming_fraud_cases,
        SUM(CASE WHEN fraud_type = 'billing_anomaly' THEN 1 ELSE 0 END) as billing_anomalies
    FROM {{ ref('f_fraud_detection') }}
    WHERE detection_timestamp >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 DAY)
),
complaint_metrics AS (
    SELECT
        COUNT(*) as total_complaints,
        SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_complaints,
        SUM(CASE WHEN resolved THEN 1 ELSE 0 END) as resolved_complaints,
        AVG(CASE WHEN resolved THEN resolution_time_days END) as avg_resolution_time,
        SUM(CASE WHEN complaint_priority = 'urgent' THEN 1 ELSE 0 END) as urgent_complaints
    FROM {{ ref('stg_complaints') }}
    WHERE posted_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
),
revenue_assurance AS (
    SELECT
        COUNT(*) as leakage_cases,
        SUM(COALESCE(estimated_revenue_loss, 0) + COALESCE(roaming_revenue_gap, 0) + ABS(COALESCE(discrepancy, 0))) as estimated_revenue_at_risk
    FROM {{ ref('f_revenue_leakage') }}
    WHERE detection_timestamp >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 30 DAY)
)

SELECT
    'customer_health' as kpi_category,
    'total_customers' as kpi_name,
    total_customers::VARCHAR as kpi_value,
    NULL as metric_type,
    NULL as trend,
    'Current total customer base' as description
FROM customer_metrics

UNION ALL

SELECT
    'customer_health' as kpi_category,
    'new_customers_30d' as kpi_name,
    new_customers::VARCHAR as kpi_value,
    NULL as metric_type,
    NULL as trend,
    'New customers acquired in last 30 days' as description
FROM customer_metrics

UNION ALL

SELECT
    'customer_health' as kpi_category,
    'churn_risk_rate' as kpi_name,
    ROUND(high_churn_risk * 100.0 / NULLIF(total_customers, 0), 2)::VARCHAR || '%' as kpi_value,
    'percentage' as metric_type,
    'increasing' as trend,
    'Percentage of customers at high churn risk' as description
FROM customer_metrics

UNION ALL

SELECT
    'financial_health' as kpi_category,
    'monthly_revenue' as kpi_name,
    '$' || ROUND(total_monthly_revenue / 1000000, 2)::VARCHAR || 'M' as kpi_value,
    'currency' as metric_type,
    'stable' as trend,
    'Total monthly revenue' as description
FROM financial_metrics

UNION ALL

SELECT
    'financial_health' as kpi_category,
    'arpu' as kpi_name,
    '$' || ROUND(avg_arpu, 2)::VARCHAR as kpi_value,
    'currency' as metric_type,
    'stable' as trend,
    'Average revenue per user' as description
FROM financial_metrics

UNION ALL

SELECT
    'network_health' as kpi_category,
    'tower_health_rate' as kpi_name,
    ROUND(healthy_towers * 100.0 / NULLIF(total_towers, 0), 2)::VARCHAR || '%' as kpi_value,
    'percentage' as metric_type,
    'stable' as trend,
    'Percentage of towers in healthy condition' as description
FROM network_metrics

UNION ALL

SELECT
    'network_health' as kpi_category,
    'avg_drop_rate' as kpi_name,
    ROUND(avg_drop_rate, 2)::VARCHAR || '%' as kpi_value,
    'percentage' as metric_type,
    'decreasing' as trend,
    'Average dropped call rate' as description
FROM network_metrics

UNION ALL

SELECT
    'fraud_detection' as kpi_category,
    'fraud_cases_30d' as kpi_name,
    fraud_cases_detected::VARCHAR as kpi_value,
    'count' as metric_type,
    'increasing' as trend,
    'Fraud cases detected in last 30 days' as description
FROM fraud_metrics

UNION ALL

SELECT
    'fraud_detection' as kpi_category,
    'critical_fraud' as kpi_name,
    critical_fraud::VARCHAR as kpi_value,
    'count' as metric_type,
    'decreasing' as trend,
    'Critical fraud cases requiring immediate action' as description
FROM fraud_metrics

UNION ALL

SELECT
    'customer_satisfaction' as kpi_category,
    'complaint_volume' as kpi_name,
    total_complaints::VARCHAR as kpi_value,
    'count' as metric_type,
    'stable' as trend,
    'Total complaints in last 30 days' as description
FROM complaint_metrics

UNION ALL

SELECT
    'customer_satisfaction' as kpi_category,
    'resolution_rate' as kpi_name,
    ROUND(resolved_complaints * 100.0 / NULLIF(total_complaints, 0), 2)::VARCHAR || '%' as kpi_value,
    'percentage' as metric_type,
    'increasing' as trend,
    'Complaint resolution rate' as description
FROM complaint_metrics

UNION ALL

SELECT
    'revenue_assurance' as kpi_category,
    'leakage_cases' as kpi_name,
    leakage_cases::VARCHAR as kpi_value,
    'count' as metric_type,
    'decreasing' as trend,
    'Revenue leakage cases detected' as description
FROM revenue_assurance

UNION ALL

SELECT
    'revenue_assurance' as kpi_category,
    'revenue_at_risk' as kpi_name,
    '$' || ROUND(estimated_revenue_at_risk / 1000, 2)::VARCHAR || 'K' as kpi_value,
    'currency' as metric_type,
    'decreasing' as trend,
    'Estimated revenue at risk from leakage' as description
FROM revenue_assurance
