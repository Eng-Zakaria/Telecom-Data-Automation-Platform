-- Cross-feed identity: CDR subscribers must resolve to billing accounts through the shared
-- subscriber_key. More than 5% unresolved means the join is broken (the original defect
-- joined CUST_ ids to hashes and matched 0%), not that a few accounts were quarantined.
SELECT orphan_share FROM (
    SELECT avg(CASE WHEN b.subscriber_key IS NULL THEN 1.0 ELSE 0 END) AS orphan_share
    FROM (SELECT DISTINCT subscriber_key FROM {{ ref('stg_cdr') }}) c
    LEFT JOIN {{ ref('stg_billing') }} b USING (subscriber_key)
) WHERE orphan_share > 0.05
