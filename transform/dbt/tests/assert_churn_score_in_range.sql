SELECT customer_id, churn_risk_score
FROM {{ ref('f_churn_prediction') }}
WHERE churn_risk_score NOT BETWEEN 0 AND 100
