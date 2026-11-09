-- Billing and usage must describe the same period, or revenue assurance compares nothing.
SELECT 'no invoice month overlaps the CDR window' AS problem
WHERE NOT EXISTS (
    SELECT 1
    FROM {{ ref('stg_billing_monthly') }} b
    JOIN {{ ref('run_context') }} r ON b.billing_month = r.as_of_month
)
