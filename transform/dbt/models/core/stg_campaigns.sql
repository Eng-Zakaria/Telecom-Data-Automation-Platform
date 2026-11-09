{{ config(materialized='view', tags=['staging', 'marketing']) }}

SELECT
    campaign_id,
    name,
    channel,
    CAST(start_date AS DATE)                    AS start_date,
    CAST(end_date AS DATE)                      AS end_date,
    date_diff('day', start_date, end_date)      AS duration_days,
    target_segment,
    budget,
    expected_reach,
    status,
    objective,
    creative_type,
    offer_details
FROM {{ source('silver', 'campaigns') }}
