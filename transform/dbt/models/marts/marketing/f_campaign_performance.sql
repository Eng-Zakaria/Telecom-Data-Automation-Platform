{{ config(
    materialized = 'table',
    tags = ['marts', 'marketing', 'campaigns']
) }}

-- Campaign Performance Analysis
-- Tracks campaign effectiveness and ROI

WITH campaign_metrics AS (
    SELECT
        c.campaign_id,
        c.name,
        c.channel,
        c.objective,
        c.target_segment,
        c.budget,
        c.start_date,
        c.end_date,
        COUNT(DISTINCT r.customer_id) as reached_customers,
        SUM(CASE WHEN r.opened THEN 1 ELSE 0 END) as opened_count,
        SUM(CASE WHEN r.clicked THEN 1 ELSE 0 END) as clicked_count,
        SUM(CASE WHEN r.converted THEN 1 ELSE 0 END) as converted_count,
        SUM(r.revenue_generated) as total_revenue,
        SUM(r.cost_incurred) as total_cost,
        AVG(r.days_to_convert) as avg_conversion_time,
        COUNT(DISTINCT r.customer_id) FILTER (WHERE r.opened) as unique_openers,
        COUNT(DISTINCT r.customer_id) FILTER (WHERE r.clicked) as unique_clickers
    FROM {{ ref('stg_campaigns') }} c
    LEFT JOIN {{ ref('stg_campaign_responses') }} r ON c.campaign_id = r.campaign_id
    GROUP BY c.campaign_id, c.name, c.channel, c.objective, c.target_segment,
             c.budget, c.start_date, c.end_date
),
channel_performance AS (
    SELECT
        channel,
        COUNT(*) as campaign_count,
        AVG(reached_customers) as avg_reach,
        AVG(opened_count * 1.0 / NULLIF(reached_customers, 0)) as avg_open_rate,
        AVG(clicked_count * 1.0 / NULLIF(opened_count, 0)) as avg_click_rate,
        AVG(converted_count * 1.0 / NULLIF(clicked_count, 0)) as avg_conversion_rate,
        SUM(total_revenue) as total_revenue,
        SUM(total_cost) as total_cost,
        SUM(total_revenue) - SUM(total_cost) as net_revenue,
        AVG((SUM(total_revenue) - SUM(total_cost)) * 1.0 / NULLIF(SUM(total_cost), 0)) as avg_roi
    FROM campaign_metrics
    GROUP BY channel
),
objective_performance AS (
    SELECT
        objective,
        COUNT(*) as campaign_count,
        AVG(reached_customers) as avg_reach,
        AVG(converted_count * 1.0 / NULLIF(reached_customers, 0)) as avg_conversion_rate,
        SUM(total_revenue) as total_revenue,
        SUM(total_cost) as total_cost,
        SUM(total_revenue) - SUM(total_cost) as net_revenue
    FROM campaign_metrics
    GROUP BY objective
),
segment_performance AS (
    SELECT
        target_segment,
        COUNT(*) as campaign_count,
        AVG(reached_customers) as avg_reach,
        AVG(converted_count * 1.0 / NULLIF(reached_customers, 0)) as avg_conversion_rate,
        SUM(total_revenue) as total_revenue,
        SUM(total_cost) as total_cost
    FROM campaign_metrics
    GROUP BY target_segment
)

SELECT
    'overall' as analysis_type,
    campaign_id,
    name,
    channel,
    objective,
    target_segment,
    budget,
    reached_customers,
    opened_count,
    clicked_count,
    converted_count,
    total_revenue,
    total_cost,
    total_revenue - total_cost as net_revenue,
    CASE WHEN total_cost > 0 THEN (total_revenue - total_cost) * 100.0 / total_cost ELSE 0 END as roi_percentage,
    avg_conversion_time,
    NULL as channel_avg_open_rate,
    NULL as channel_avg_conversion_rate,
    NULL as objective_avg_conversion_rate,
    NULL as segment_avg_conversion_rate
FROM campaign_metrics

UNION ALL

SELECT
    'channel' as analysis_type,
    NULL as campaign_id,
    NULL as name,
    channel,
    NULL as objective,
    NULL as target_segment,
    NULL as budget,
    avg_reach as reached_customers,
    NULL as opened_count,
    NULL as clicked_count,
    NULL as converted_count,
    total_revenue,
    total_cost,
    net_revenue,
    avg_roi as roi_percentage,
    NULL as avg_conversion_time,
    channel_avg_open_rate,
    channel_avg_conversion_rate,
    NULL as objective_avg_conversion_rate,
    NULL as segment_avg_conversion_rate
FROM (
    SELECT *,
           AVG(avg_open_rate) OVER (PARTITION BY channel) as channel_avg_open_rate,
           AVG(avg_conversion_rate) OVER (PARTITION BY channel) as channel_avg_conversion_rate
    FROM channel_performance
) cp

UNION ALL

SELECT
    'objective' as analysis_type,
    NULL as campaign_id,
    NULL as name,
    NULL as channel,
    objective,
    NULL as target_segment,
    NULL as budget,
    avg_reach as reached_customers,
    NULL as opened_count,
    NULL as clicked_count,
    NULL as converted_count,
    total_revenue,
    total_cost,
    net_revenue,
    NULL as roi_percentage,
    NULL as avg_conversion_time,
    NULL as channel_avg_open_rate,
    NULL as channel_avg_conversion_rate,
    objective_avg_conversion_rate,
    NULL as segment_avg_conversion_rate
FROM objective_performance

UNION ALL

SELECT
    'segment' as analysis_type,
    NULL as campaign_id,
    NULL as name,
    NULL as channel,
    NULL as objective,
    target_segment,
    NULL as budget,
    avg_reach as reached_customers,
    NULL as opened_count,
    NULL as clicked_count,
    NULL as converted_count,
    total_revenue,
    total_cost,
    NULL as net_revenue,
    NULL as roi_percentage,
    NULL as avg_conversion_time,
    NULL as channel_avg_open_rate,
    NULL as channel_avg_conversion_rate,
    NULL as objective_avg_conversion_rate,
    segment_avg_conversion_rate
FROM segment_performance
