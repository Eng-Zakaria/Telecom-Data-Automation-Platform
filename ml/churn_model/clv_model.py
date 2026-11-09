"""
Customer Lifetime Value (CLV) Model

Predicts the total revenue a customer will generate over their lifetime:
- Probabilistic CLV (BG/NBD model)
- Regression-based CLV
- cohort-based analysis
- ROI calculation for retention campaigns
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
from datetime import datetime, timedelta


@dataclass
class CLVPrediction:
    """CLV prediction result"""
    customer_id: str
    predicted_clv: float
    confidence_interval: Tuple[float, float]
    prediction_horizon_months: int
    segment: str
    prediction_date: str


class CLVModel:
    """
    Customer Lifetime Value prediction model.

    Methods:
    - Parametric CLV (Beta Geometric / Negative Binomial Distribution)
    - Regression-based CLV
    - Cohort-based CLV
    - Predictive CLV with uncertainty intervals
    """

    def __init__(
        self,
        model_dir: str = "ml/churn_model/clv",
        default_horizon_months: int = 12,
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.default_horizon_months = default_horizon_months

        # Model parameters (will be fitted)
        self.r = 1.0  # BG/NBD parameter
        self.alpha = 1.0
        self.beta = 1.0
        self.nu = 1.0  # Gamma parameter for monetary value
        self.sigma = 1.0  # Gamma parameter for monetary value

        # Historical data for calibration
        self.calibration_data = None
        self.segment_clv = {}

    def fit(
        self,
        df: pd.DataFrame,
        customer_id_col: str = "customer_id",
        recency_col: str = "days_since_last_purchase",
        frequency_col: str = "purchase_frequency",
        monetary_col: str = "average_monetary_value",
        t_col: str = "customer_age_days",
    ):
        """
        Fit CLV model on historical data.

        Args:
            df: Historical customer data
            customer_id_col: Column name for customer ID
            recency_col: Column name for recency (days since last purchase)
            frequency_col: Column name for frequency (number of purchases)
            monetary_col: Column name for monetary value
            t_col: Column name for customer age (days since first purchase)
        """
        self.calibration_data = df.copy()

        # Fit BG/NBD parameters using maximum likelihood estimation
        # Simplified approach - in production would use scipy.optimize
        recency = df[recency_col].values
        frequency = df[frequency_col].values
        t = df[t_col].values
        monetary = df[monetary_col].values

        # Estimate parameters (simplified MLE)
        avg_monetary = monetary.mean()
        avg_recency = recency.mean()
        avg_frequency = frequency.mean()

        # Rough parameter estimation
        self.r = max(0.5, avg_frequency / 10)
        self.alpha = max(1.0, avg_monetary / 100)
        self.beta = max(1.0, t.mean() / 365)
        self.nu = max(1.0, avg_monetary)
        self.sigma = max(0.5, avg_monetary * 0.2)

        # Store segment-level CLV
        if "segment" in df.columns:
            for segment in df["segment"].unique():
                segment_data = df[df["segment"] == segment]
                self.segment_clv[segment] = segment_data[monetary_col].mean() * \
                                           self._expected_repeat_transactions(
                                               segment_data[recency_col].mean(),
                                               segment_data[frequency_col].mean(),
                                               segment_data[t_col].mean(),
                                           )

    def predict(
        self,
        customer_data: pd.DataFrame,
        horizon_months: int = None,
        customer_ids: Optional[List[str]] = None,
    ) -> List[CLVPrediction]:
        """
        Predict CLV for customers.

        Args:
            customer_data: Customer data with recency, frequency, monetary values
            horizon_months: Prediction horizon in months
            customer_ids: Optional customer IDs

        Returns:
            List of CLVPrediction objects
        """
        if horizon_months is None:
            horizon_months = self.default_horizon_months

        if customer_ids is None:
            customer_ids = customer_data.get("customer_id",
                [f"CUST_{i:06d}" for i in range(len(customer_data))])

        predictions = []

        for idx, row in customer_data.iterrows():
            # Get customer-specific parameters or use defaults
            recency = row.get("days_since_last_purchase", 30)
            frequency = row.get("purchase_frequency", 5)
            monetary = row.get("average_monetary_value", 150)
            t = row.get("customer_age_days", 365)
            segment = row.get("segment", "unknown")

            # Calculate CLV
            expected_transactions = self._expected_repeat_transactions(
                recency, frequency, t
            )
            clv = expected_transactions * monetary * (horizon_months / 12)

            # Calculate confidence interval
            ci_lower = clv * 0.8  # Simplified 80% CI
            ci_upper = clv * 1.2

            predictions.append(CLVPrediction(
                customer_id=str(customer_ids[idx] if idx < len(customer_ids) else f"CUST_{idx:06d}"),
                predicted_clv=float(clv),
                confidence_interval=(float(ci_lower), float(ci_upper)),
                prediction_horizon_months=horizon_months,
                segment=segment,
                prediction_date=datetime.now().isoformat(),
            ))

        return predictions

    def _expected_repeat_transactions(
        self,
        recency: float,
        frequency: float,
        t: float,
    ) -> float:
        """
        Calculate expected number of future transactions.

        Uses simplified BG/NBD model.
        """
        if t <= 0:
            return 0

        # Annual transaction rate
        lambda_annual = (frequency + 1) / (t / 365 + 1)

        # Probability of being alive (not churned)
        # Simplified survival function
        survival_prob = np.exp(-0.01 * (t / 365))

        # Expected future transactions
        expected = lambda_annual * survival_prob

        return max(0.1, expected)

    def cohort_analysis(
        self,
        df: pd.DataFrame,
        cohort_col: str = "signup_month",
        metric_col: str = "revenue",
    ) -> pd.DataFrame:
        """
        Perform cohort-based CLV analysis.

        Args:
            df: Customer data with signup dates
            cohort_col: Column for cohort grouping
            metric_col: Column for revenue metric

        Returns:
            DataFrame with cohort CLV analysis
        """
        cohorts = df.groupby(cohort_col).agg({
            metric_col: ["sum", "mean", "count"],
        }).reset_index()

        cohorts.columns = [cohort_col, "total_revenue", "avg_revenue", "n_customers"]
        cohorts["clv"] = cohorts["total_revenue"] / cohorts["n_customers"]

        return cohorts

    def get_segment_clv(self) -> Dict[str, float]:
        """Get average CLV by segment"""
        return self.segment_clv

    def calculate_roi(
        self,
        campaign_cost: float,
        target_customers: int,
        retention_improvement: float,
    ) -> Dict:
        """
        Calculate ROI for retention campaign.

        Args:
            campaign_cost: Total campaign cost
            target_customers: Number of customers targeted
            retention_improvement: Improvement in retention rate (e.g., 0.05 for 5%)

        Returns:
            ROI metrics
        """
        avg_clv = np.mean(list(self.segment_clv.values())) if self.segment_clv else 1500
        preserved_revenue = target_customers * avg_clv * retention_improvement
        roi = (preserved_revenue - campaign_cost) / campaign_cost * 100

        return {
            "campaign_cost": campaign_cost,
            "target_customers": target_customers,
            "avg_clv": avg_clv,
            "preserved_revenue": preserved_revenue,
            "roi_percent": roi,
            "net_value": preserved_revenue - campaign_cost,
        }


def generate_clv_data(
    n_samples: int = 5000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic data for CLV modeling"""
    rng = np.random.default_rng(random_state)

    data = {
        "customer_id": [f"CUST_{i:06d}" for i in range(n_samples)],
        "days_since_last_purchase": rng.exponential(30, n_samples).clip(1, 365),
        "purchase_frequency": rng.poisson(10, n_samples).clip(1, 100),
        "average_monetary_value": rng.lognormal(4.5, 0.5, n_samples).clip(50, 1000),
        "customer_age_days": rng.exponential(365, n_samples).clip(30, 1825),
        "segment": rng.choice(
            ["platinum", "gold", "silver", "bronze"],
            n_samples,
            p=[0.1, 0.25, 0.4, 0.25]
        ),
        "signup_month": [rng.choice(pd.date_range("2023-01-01", periods=12, freq="MS").strftime("%Y-%m").tolist()) for _ in range(n_samples)],
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training CLV Model...")

    # Generate data
    df = generate_clv_data(n_samples=5000)
    print(f"Generated {len(df)} customer records")

    # Initialize and fit model
    clv_model = CLVModel()
    clv_model.fit(df)

    # Predict CLV
    predictions = clv_model.predict(df.head(10))
    for pred in predictions[:5]:
        print(f"  {pred.customer_id}: CLV=${pred.predicted_clv:.2f} "
              f"({pred.segment})")

    # Cohort analysis
    cohorts = clv_model.cohort_analysis(df)
    print(f"\nCohort CLV Analysis:")
    print(cohorts.head())

    # ROI calculation
    roi = clv_model.calculate_roi(
        campaign_cost=10000,
        target_customers=1000,
        retention_improvement=0.05
    )
    print(f"\nCampaign ROI: {roi['roi_percent']:.1f}%")
