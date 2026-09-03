{{ config(
    materialized = 'table',
    tags = ['core', 'dimension']
) }}

-- Tower Dimension Table
-- Master data for all cell towers with geographic and operator info

SELECT
    tower_id,
    tower_type,
    operator,
    country_code,
    city,
    geographic_lat as latitude,
    geographic_lon as longitude,
    CASE
        WHEN tower_type = 'macro' THEN 'macro_cell'
        WHEN tower_type = 'micro' THEN 'micro_cell'
        WHEN tower_type = 'pico' THEN 'pico_cell'
        ELSE 'unknown'
    END as tower_category,
    CASE
        WHEN city = 'Riyadh' THEN 'central'
        WHEN city LIKE '%Jeddah%' THEN 'western'
        WHEN city LIKE '%Dammam%' THEN 'eastern'
        ELSE 'other'
    END as region,
    CURRENT_TIMESTAMP as dim_updated_timestamp
FROM {{ ref('stg_cdr') }}
WHERE tower_id IS NOT NULL
GROUP BY tower_id, tower_type, operator, country_code, city, geographic_lat, geographic_lon

UNION

SELECT
    tower_id,
    tower_type,
    operator,
    country_code,
    city,
    NULL as latitude,
    NULL as longitude,
    CASE
        WHEN tower_type = 'macro' THEN 'macro_cell'
        WHEN tower_type = 'micro' THEN 'micro_cell'
        WHEN tower_type = 'pico' THEN 'pico_cell'
        ELSE 'unknown'
    END as tower_category,
    'central' as region,
    CURRENT_TIMESTAMP as dim_updated_timestamp
FROM {{ ref('stg_network_kpi') }}
WHERE tower_id NOT IN (SELECT tower_id FROM {{ this }})
GROUP BY tower_id, tower_type, operator, country_code, city
