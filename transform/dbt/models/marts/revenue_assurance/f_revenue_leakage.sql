{{ config(
    materialized = 'table',
    tags = ['marts', 'revenue_assurance', 'leakage']
) }}

-- Revenue Leakage Detection
-- Identifies potential revenue losses from billing errors and fraud

WITH usage_vs_billing AS (
    SELECT
        b.customer_id,
        b.billing_month,
        b.total_charge as billed_amount,
        COALESCE(SUM(CASE WHEN c.call_type = 'voice' THEN c.duration_seconds * 0.05 ELSE 0 END), 0) as calculated_voice_charges,
        COALESCE(SUM(CASE WHEN c.call_type = 'sms' THEN 0.10 ELSE 0 END), 0) as calculated_sms_charges,
        COALESCE(SUM(CASE WHEN c.call_type = 'data' THEN c.data_volume_mb * 0.50 ELSE 0 END), 0) as calculated_data_charges,
        COUNT(*) as total_calls,
        SUM(c.duration_seconds) as total_call_duration,
        SUM(c.data_volume_mb) as total_data_used
    FROM {{ ref('stg_billing_monthly') }} b
    LEFT JOIN {{ ref('stg_cdr') }} c ON b.customer_id = c.caller_id
        AND DATE(c.start_time) >= DATE_FORMAT(DATE_ADD(DATE(b.billing_month), -1), '%Y-%m-01')
        AND DATE(c.start_time) < DATE_FORMAT(b.billing_month, '%Y-%m-01')
    WHERE b.billing_month = DATE_FORMAT(DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH), '%Y-%m')
    GROUP BY b.customer_id, b.billing_month, b.total_charge
),
discrepancies AS (
    SELECT
        customer_id,
        billing_month,
        billed_amount,
        calculated_voice_charges,
        calculated_sms_charges,
        calculated_data_charges,
        (calculated_voice_charges + calculated_sms_charges + calculated_data_charges) as calculated_total,
        billed_amount - (calculated_voice_charges + calculated_sms_charges + calculated_data_charges) as discrepancy,
        CASE
            WHEN billed_amount < (calculated_voice_charges + calculated_sms_charges + calculated_data_charges) * 0.8
            THEN 'under_billed'
            WHEN billed_amount > (calculated_voice_charges + calculated_sms_charges + calculated_data_charges) * 1.2
            THEN 'over_billed'
            ELSE 'within_tolerance'
        END as billing_accuracy
    FROM usage_vs_billing
),
zero_rating_abuse AS (
    SELECT
        caller_id as customer_id,
        COUNT(*) as zero_rating_calls,
        SUM(duration_seconds) as total_zero_rating_duration,
        SUM(CASE WHEN call_type = 'voice' THEN duration_seconds * 0.05
                 WHEN call_type = 'data' THEN data_volume_mb * 0.50
                 ELSE 0 END) as estimated_revenue_loss
    FROM {{ ref('stg_cdr') }}
    WHERE charging_key = 0 AND start_time >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    GROUP BY caller_id
    HAVING COUNT(*) > 10
),
roaming_revenue_gap AS (
    SELECT
        customer_id,
        SUM(settlement_amount) as total_settlement_cost,
        SUM(settlement_amount * 2.5) as estimated_revenue,
        SUM(settlement_amount * 1.5) as revenue_gap
    FROM {{ ref('stg_roaming_sessions') }}
    WHERE start_time >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
    GROUP BY customer_id
    HAVING SUM(settlement_amount * 1.5) > 100
)

SELECT
    customer_id,
    billing_month,
    billed_amount,
    calculated_total,
    discrepancy,
    billing_accuracy,
    zero_rating_calls,
    total_zero_rating_duration,
    estimated_revenue_loss as zero_rating_loss,
    total_settlement_cost,
    estimated_revenue,
    revenue_gap as roaming_revenue_gap,
    COALESCE(estimated_revenue_loss, 0) + COALESCE(roaming_revenue_gap, 0) + ABS(COALESCE(discrepancy, 0)) as total_estimated_leakage,
    CURRENT_TIMESTAMP as detection_timestamp
FROM discrepancies
LEFT JOIN (
    SELECT customer_id, zero_rating_calls, total_zero_rating_duration, estimated_revenue_loss
    FROM zero_rating_abuse
) zra ON discrepancies.customer_id = zra.customer_id
LEFT JOIN (
    SELECT customer_id, total_settlement_cost, estimated_revenue, revenue_gap
    FROM roaming_revenue_gap
) rrg ON discrepancies.customer_id = rrg.customer_id
WHERE billing_accuracy != 'within_tolerance'
   OR zero_rating_calls IS NOT NULL
   OR revenue_gap IS NOT NULL
