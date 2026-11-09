{{ config(
    materialized = 'table',
    tags = ['core', 'billing']
) }}

-- One row per subscriber: payment behaviour across their invoice history.
-- (Plan-level revenue lives in f_plan_performance / gold.revenue_by_plan; mixing two
--  grains in one table, as the original UNION did, breaks every aggregate on top of it.)

WITH monthly AS (
    SELECT * FROM {{ ref('stg_billing_monthly') }}
),
latest_month AS (
    SELECT max(billing_month) AS billing_month FROM monthly
)

SELECT
    m.customer_id,
    any_value(m.subscriber_key)                                                  AS subscriber_key,
    any_value(m.plan_id)                                                         AS plan_id,
    max(CASE WHEN m.billing_month = l.billing_month THEN m.total_charge END)     AS current_month_charge,
    avg(m.total_charge)                                                          AS avg_monthly_charge,
    sum(m.total_charge)                                                          AS total_billed,
    count(*) FILTER (WHERE m.payment_status = 'paid')                           AS paid_months,
    count(*) FILTER (WHERE m.payment_status = 'overdue')                        AS overdue_months,
    count(*) FILTER (WHERE m.payment_status = 'defaulted')                      AS defaulted_months,
    count(DISTINCT m.billing_month)                                              AS num_billing_months,
    CASE
        WHEN count(*) FILTER (WHERE m.payment_status = 'defaulted') > 0 THEN 'defaulted'
        WHEN count(*) FILTER (WHERE m.payment_status = 'overdue') > 0 THEN 'at_risk'
        WHEN count(*) FILTER (WHERE m.payment_status = 'paid') = count(DISTINCT m.billing_month)
            THEN 'good_standing'
        ELSE 'needs_attention'
    END                                                                          AS payment_health,
    CURRENT_TIMESTAMP                                                            AS gold_ingestion_timestamp
FROM monthly m
CROSS JOIN latest_month l
GROUP BY m.customer_id
