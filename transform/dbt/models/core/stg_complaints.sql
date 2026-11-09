{{ config(
    materialized = 'view',
    tags = ['staging', 'complaints']
) }}

-- Staging layer for Complaint data
-- Cleans and standardizes complaint records

SELECT
    complaint_id,
    source,
    platform,
    language,
    category,
    sentiment,
    severity,
    title,
    description,
    posted_date,
    resolved,
    resolution_time_days,
    upvotes,
    customer_id_hash,
    customer_id_hash AS subscriber_key,
    CASE
        WHEN sentiment = 'negative' AND severity IN ('high', 'critical') THEN 'urgent'
        WHEN sentiment = 'negative' AND severity = 'medium' THEN 'attention'
        WHEN sentiment = 'neutral' THEN 'monitor'
        ELSE 'positive'
    END as complaint_priority,
    CASE
        WHEN category = 'billing' THEN 'billing_issue'
        WHEN category = 'network' THEN 'network_issue'
        WHEN category = 'customer_service' THEN 'service_issue'
        WHEN category = 'roaming' THEN 'roaming_issue'
        WHEN category = 'product' THEN 'product_issue'
        ELSE 'other'
    END as issue_type,
    CASE
        WHEN language = 'ar' THEN 'arabic'
        ELSE 'english'
    END as language_full,
    CURRENT_TIMESTAMP as staging_ingestion_timestamp
FROM {{ source('silver', 'complaints') }}
WHERE complaint_id IS NOT NULL
