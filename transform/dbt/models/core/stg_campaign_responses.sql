{{ config(materialized='view', tags=['staging', 'marketing']) }}

SELECT
    response_id,
    campaign_id,
    customer_id,
    hashed_id                                   AS subscriber_key,
    CAST(sent_date AS DATE)                     AS sent_date,
    opened,
    clicked,
    converted,
    nullif(conversion_type, 'None')             AS conversion_type,
    revenue_generated,
    cost_incurred,
    attribution_channel,
    days_to_convert
FROM {{ source('silver', 'campaign_responses') }}
