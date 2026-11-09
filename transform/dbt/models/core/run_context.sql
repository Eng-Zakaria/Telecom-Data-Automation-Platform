{{ config(materialized='table', tags=['core']) }}

-- One row describing the batch being modelled. Marts filter relative to as_of_date
-- (see macros/as_of.sql) instead of the wall clock.
SELECT
    CAST(max(start_time) AS DATE)                AS as_of_date,
    strftime(max(start_time), '%Y-%m')           AS as_of_month,
    CAST(min(start_time) AS DATE)                AS window_start,
    count(*)                                     AS cdr_rows,
    CURRENT_TIMESTAMP                            AS built_at
FROM {{ source('silver', 'cdr') }}
