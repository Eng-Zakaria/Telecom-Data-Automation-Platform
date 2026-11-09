{{ config(materialized='table', tags=['core', 'dimension']) }}

SELECT
    partner_id,
    name,
    country_code,
    mcc,
    mnc,
    mcc || '-' || mnc                           AS plmn_id,
    settlement_rate_per_min,
    settlement_rate_per_mb,
    agreement_type,
    status,
    status = 'active'                           AS is_active
FROM {{ source('silver', 'roaming_partners') }}
