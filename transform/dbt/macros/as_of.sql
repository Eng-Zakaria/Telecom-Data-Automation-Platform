{# The point in time every mart is computed "as of": the latest event in the data, not the
   wall clock. Keeps synthetic/backfilled batches meaningful and runs reproducible.
   Override with --vars '{as_of_date: 2024-01-31}'. #}
{% macro as_of_date() -%}
  {%- if var('as_of_date', none) -%}
    CAST('{{ var("as_of_date") }}' AS DATE)
  {%- else -%}
    (SELECT as_of_date FROM {{ ref('run_context') }})
  {%- endif -%}
{%- endmacro %}

{% macro as_of_month() -%}
  strftime({{ as_of_date() }}, '%Y-%m')
{%- endmacro %}

{# Pseudonymous subscriber key shared by every feed: sha256('CUST_nnnnnn')[:16] #}
{% macro subscriber_key(customer_id_col) -%}
  left(sha256({{ customer_id_col }}), 16)
{%- endmacro %}
