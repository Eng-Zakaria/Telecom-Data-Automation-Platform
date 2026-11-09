{{ config(
    materialized = 'table',
    tags = ['marts', 'revenue_assurance']
) }}

-- Revenue assurance: where does rated usage not match what was billed?
-- Three leakage signals per subscriber for the as-of invoice month:
--   1. billing discrepancy  (rated CDR usage vs invoiced usage charge, +/-20% tolerance)
--   2. zero-rated usage      (charging_key = 0 on billable traffic)
--   3. roaming margin gap    (partner settlement cost not recovered at retail)
-- Every CTE is keyed on subscriber_key, the pseudonymous id shared by all feeds.

{% set voice_rate_per_sec = 0.05 / 60 %}
{% set sms_rate = 0.10 %}
{% set data_rate_per_mb = 0.01 %}
{% set roaming_retail_markup = 2.5 %}

WITH invoice_month AS (
    SELECT max(billing_month) AS billing_month FROM {{ ref('stg_billing_monthly') }}
),

-- The CDR window can cover only part of a month: scale rated usage up to a full month
-- before comparing it with the invoice, or every invoice looks over-billed.
coverage AS (
    SELECT
        strftime(date_trunc('month', start_time), '%Y-%m')                         AS billing_month,
        count(DISTINCT CAST(start_time AS DATE))                                    AS observed_days,
        any_value(day(last_day(start_time)))                                        AS days_in_month
    FROM {{ ref('stg_cdr') }}
    GROUP BY 1
),

rated_usage_raw AS (
    SELECT
        c.subscriber_key,
        strftime(date_trunc('month', c.start_time), '%Y-%m')                       AS billing_month,
        count(*)                                                                    AS events,
        sum(CASE WHEN c.call_type = 'voice' THEN c.duration_seconds END)            AS voice_seconds,
        sum(c.data_volume_mb)                                                       AS data_mb,
        sum(CASE WHEN c.call_type = 'voice' THEN c.duration_seconds * {{ voice_rate_per_sec }}
                 WHEN c.call_type = 'sms'   THEN {{ sms_rate }}
                 WHEN c.call_type = 'data'  THEN c.data_volume_mb * {{ data_rate_per_mb }}
                 ELSE 0 END)                                                        AS rated_amount_observed
    FROM {{ ref('stg_cdr') }} c
    GROUP BY ALL
),

rated_usage AS (
    SELECT
        u.*,
        v.observed_days,
        u.rated_amount_observed * v.days_in_month / v.observed_days                AS rated_amount
    FROM rated_usage_raw u
    JOIN coverage v USING (billing_month)
),

discrepancies AS (
    SELECT
        b.customer_id,
        b.subscriber_key,
        b.billing_month,
        b.usage_charge                                                              AS billed_usage,
        coalesce(u.rated_amount, 0)                                                 AS rated_usage,
        coalesce(u.events, 0)                                                       AS usage_events,
        u.observed_days,
        b.usage_charge - coalesce(u.rated_amount, 0)                                AS discrepancy,
        CASE
            WHEN u.rated_amount IS NULL THEN 'no_usage_recorded'
            WHEN b.usage_charge < u.rated_amount * 0.8 THEN 'under_billed'
            WHEN b.usage_charge > u.rated_amount * 1.2 THEN 'over_billed'
            ELSE 'within_tolerance'
        END                                                                         AS billing_accuracy
    FROM {{ ref('stg_billing_monthly') }} b
    JOIN invoice_month m USING (billing_month)
    LEFT JOIN rated_usage u USING (subscriber_key, billing_month)
),

zero_rated AS (
    SELECT
        subscriber_key,
        count(*)                                                                    AS zero_rated_events,
        sum(duration_seconds)                                                       AS zero_rated_seconds,
        sum(CASE WHEN call_type = 'voice' THEN duration_seconds * {{ voice_rate_per_sec }}
                 WHEN call_type = 'data'  THEN data_volume_mb * {{ data_rate_per_mb }}
                 ELSE 0 END)                                                        AS zero_rated_loss
    FROM {{ ref('stg_cdr') }}
    WHERE charging_key = 0
      AND start_time >= {{ as_of_date() }} - INTERVAL 30 DAY
    GROUP BY subscriber_key
),

roaming_gap AS (
    SELECT
        subscriber_key,
        sum(settlement_amount)                                                      AS settlement_cost,
        sum(settlement_amount) * {{ roaming_retail_markup }}                        AS expected_retail,
        sum(settlement_amount) * ({{ roaming_retail_markup }} - 1)                  AS roaming_margin_at_risk
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= {{ as_of_date() }} - INTERVAL 30 DAY
    GROUP BY subscriber_key
)

SELECT
    d.customer_id,
    d.subscriber_key,
    d.billing_month,
    d.billed_usage,
    d.rated_usage,
    d.usage_events,
    d.observed_days,
    d.discrepancy,
    d.billing_accuracy,
    z.zero_rated_events,
    z.zero_rated_seconds,
    z.zero_rated_loss,
    r.settlement_cost              AS roaming_settlement_cost,
    r.roaming_margin_at_risk,
    greatest(-coalesce(d.discrepancy, 0), 0)        -- only under-billing is leakage
      + coalesce(z.zero_rated_loss, 0)
      + coalesce(r.roaming_margin_at_risk, 0)       AS total_estimated_leakage,
    CURRENT_TIMESTAMP              AS detection_timestamp
FROM discrepancies d
LEFT JOIN zero_rated z USING (subscriber_key)
LEFT JOIN roaming_gap r USING (subscriber_key)
WHERE d.billing_accuracy <> 'within_tolerance'
   OR z.zero_rated_events IS NOT NULL
   OR r.settlement_cost IS NOT NULL
