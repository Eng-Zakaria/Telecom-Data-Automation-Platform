-- f_customers must have exactly one row per billing account: no fan-out from the joins.
SELECT * FROM (
    SELECT (SELECT count(*) FROM {{ ref('f_customers') }})  AS customers_360,
           (SELECT count(*) FROM {{ ref('stg_billing') }}) AS billing_accounts
) WHERE customers_360 <> billing_accounts
