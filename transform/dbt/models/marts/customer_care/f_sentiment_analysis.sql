{{ config(
    materialized = 'table',
    tags = ['marts', 'customer_care', 'sentiment']
) }}

-- Sentiment Analysis Dashboard
-- Analyzes customer complaints and feedback by sentiment and category

WITH complaint_analysis AS (
    SELECT
        c.language,
        c.category,
        c.sentiment,
        c.severity,
        c.complaint_priority,
        c.issue_type,
        COUNT(*) as complaint_count,
        AVG(c.upvotes) as avg_upvotes,
        SUM(CASE WHEN c.resolved THEN 1 ELSE 0 END) as resolved_count,
        AVG(CASE WHEN c.resolved THEN c.resolution_time_days END) as avg_resolution_time,
        MIN(c.posted_date) as first_complaint_date,
        MAX(c.posted_date) as last_complaint_date
    FROM {{ ref('stg_complaints') }} c
    WHERE c.posted_date >= ({{ as_of_date() }} - INTERVAL 90 DAY)
    GROUP BY c.language, c.category, c.sentiment, c.severity,
             c.complaint_priority, c.issue_type
),
trend_analysis AS (
    SELECT
        CAST(posted_date AS DATE) as date,
        sentiment,
        COUNT(*) as daily_count
    FROM {{ ref('stg_complaints') }}
    WHERE posted_date >= ({{ as_of_date() }} - INTERVAL 30 DAY)
    GROUP BY CAST(posted_date AS DATE), sentiment
),
source_breakdown AS (
    SELECT
        source,
        platform,
        COUNT(*) as complaint_count,
        AVG(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_ratio,
        AVG(upvotes) as avg_engagement
    FROM {{ ref('stg_complaints') }}
    WHERE posted_date >= ({{ as_of_date() }} - INTERVAL 30 DAY)
    GROUP BY source, platform
),
customer_impact AS (
    SELECT
        c.customer_id_hash,
        COUNT(DISTINCT c.complaint_id) as total_complaints,
        COUNT(DISTINCT CASE WHEN c.sentiment = 'negative' THEN c.complaint_id END) as negative_complaints,
        AVG(CASE WHEN c.resolved THEN c.resolution_time_days END) as avg_resolution_time,
        MAX(c.posted_date) as last_contact_date,
        COUNT(DISTINCT c.category) as complaint_categories
    FROM {{ ref('stg_complaints') }} c
    WHERE c.posted_date >= ({{ as_of_date() }} - INTERVAL 180 DAY)
    GROUP BY c.customer_id_hash
    HAVING COUNT(DISTINCT c.complaint_id) > 1
)

SELECT
    'category_sentiment' as analysis_type,
    language,
    category,
    sentiment,
    severity,
    complaint_count,
    avg_upvotes,
    resolved_count,
    avg_resolution_time,
    NULL as date,
    NULL as daily_count,
    NULL as source,
    NULL as platform,
    NULL as total_complaints,
    NULL as negative_complaints
FROM complaint_analysis

UNION ALL

SELECT
    'daily_trend' as analysis_type,
    NULL as language,
    NULL as category,
    sentiment,
    NULL as severity,
    daily_count as complaint_count,
    NULL as avg_upvotes,
    NULL as resolved_count,
    NULL as avg_resolution_time,
    date,
    daily_count,
    NULL as source,
    NULL as platform,
    NULL as total_complaints,
    NULL as negative_complaints
FROM trend_analysis

UNION ALL

SELECT
    'source_breakdown' as analysis_type,
    NULL as language,
    NULL as category,
    NULL as sentiment,
    NULL as severity,
    complaint_count,
    avg_engagement as avg_upvotes,
    NULL as resolved_count,
    NULL as avg_resolution_time,
    NULL as date,
    NULL as daily_count,
    source,
    platform,
    NULL as total_complaints,
    NULL as negative_complaints
FROM source_breakdown

UNION ALL

SELECT
    'customer_impact' as analysis_type,
    NULL as language,
    NULL as category,
    NULL as sentiment,
    NULL as severity,
    total_complaints as complaint_count,
    NULL as avg_upvotes,
    NULL as resolved_count,
    avg_resolution_time,
    NULL as date,
    NULL as daily_count,
    NULL as source,
    NULL as platform,
    total_complaints,
    negative_complaints
FROM customer_impact
