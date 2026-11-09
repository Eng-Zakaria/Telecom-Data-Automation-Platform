{{ config(severity='warn') }}
-- Lists CDR subscribers with no billing account. A few are expected when the billing
-- contract quarantines bad accounts; they surface as a warning with the exact keys.
-- The hard failure lives in assert_orphan_usage_below_threshold.
SELECT c.subscriber_key, count(*) AS cdr_events
FROM {{ ref('stg_cdr') }} c
LEFT JOIN {{ ref('stg_billing') }} b USING (subscriber_key)
WHERE b.subscriber_key IS NULL
GROUP BY 1
