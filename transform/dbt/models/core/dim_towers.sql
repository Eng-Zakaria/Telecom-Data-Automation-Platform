{{ config(
    materialized = 'table',
    tags = ['core', 'dimension']
) }}

-- Tower dimension from the shared tower registry, enriched with what each cell carried.

WITH traffic AS (
    SELECT cell_tower_id AS tower_id,
           count(*)                       AS cdr_events,
           count(DISTINCT subscriber_key) AS distinct_subscribers
    FROM {{ ref('stg_cdr') }}
    GROUP BY 1
)

SELECT
    t.tower_id,
    t.tower_type,
    t.operator,
    t.country_code,
    t.city,
    t.lat AS latitude,
    t.lon AS longitude,
    CASE t.tower_type
        WHEN 'macro' THEN 'macro_cell'
        WHEN 'micro' THEN 'micro_cell'
        WHEN 'pico' THEN 'pico_cell'
        ELSE 'unknown'
    END AS tower_category,
    CASE
        WHEN t.city = 'Riyadh' THEN 'central'
        WHEN t.city LIKE '%Jeddah%' THEN 'western'
        WHEN t.city LIKE '%Dammam%' THEN 'eastern'
        ELSE 'other'
    END AS region,
    coalesce(x.cdr_events, 0)           AS cdr_events,
    coalesce(x.distinct_subscribers, 0) AS distinct_subscribers,
    CURRENT_TIMESTAMP AS dim_updated_timestamp
FROM {{ source('silver', 'towers') }} t
LEFT JOIN traffic x USING (tower_id)
