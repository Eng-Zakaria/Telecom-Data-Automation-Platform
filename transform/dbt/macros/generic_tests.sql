{# Small generic tests so the project needs no package download (dbt deps) to run in CI. #}

{% test unique_combination(model, columns) %}
SELECT {{ columns | join(', ') }}, count(*) AS n
FROM {{ model }}
GROUP BY {{ columns | join(', ') }}
HAVING count(*) > 1
{% endtest %}

{% test dbt_utils_free_single_row(model) %}
SELECT n FROM (SELECT count(*) AS n FROM {{ model }}) WHERE n <> 1
{% endtest %}
