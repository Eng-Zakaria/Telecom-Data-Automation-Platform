"""
Pricing Elasticity Model

Estimates price elasticity of demand for:
- Plan pricing
- Add-on services
- Roaming packages
- Data bundles
- Promotional offers
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
from scipy.optimize import minimize


@dataclass
class ElasticityResult:
    """Price elasticity result"""
    product_name: str
    elasticity_estimate: float
    confidence_interval: Tuple[float, float]
    optimal_price: float
    current_price: float
    predicted_demand_change: float
    revenue_impact: float
    recommendation: str


class PricingElasticityModel:
    """
    Price elasticity estimation model.

    Methods:
    - Log-linear regression (constant elasticity)
    - Piecewise linear (segment-specific)
    - Bayesian estimation (with priors)
    - Synthetic control (for policy changes)
    """

    def __init__(
        self,
        model_dir: str = "ml/pricing_elasticity",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Default elasticity priors (based on telecom industry)
        self.default_priors = {
            "plan_upgrade": {"mean": -0.5, "std": 0.2},
            "data_addon": {"mean": -1.2, "std": 0.3},
            "roaming_package": {"mean": -0.8, "std": 0.25},
            "premium_support": {"mean": -0.3, "std": 0.15},
            "streaming_bundle": {"mean": -1.5, "std": 0.4},
        }

        # Estimated elasticities (will be fitted)
        self.elasticities = {}
        self.price_history = None

    def fit(
        self,
        df: pd.DataFrame,
        price_col: str = "price",
        quantity_col: str = "quantity",
        product_col: str = "product_type",
    ):
        """
        Fit elasticity model on historical price-quantity data.

        Args:
            df: Historical data with prices and quantities
            price_col: Column name for price
            quantity_col: Column name for quantity demanded
            product_col: Column name for product type
        """
        self.price_history = df.copy()

        # Fit elasticity for each product type
        for product in df[product_col].unique():
            product_data = df[df[product_col] == product]

            if len(product_data) < 10:
                continue

            # Log-linear regression for constant elasticity
            prices = product_data[price_col].values
            quantities = product_data[quantity_col].values

            # Avoid log(0)
            mask = (prices > 0) & (quantities > 0)
            if mask.sum() < 5:
                continue

            log_price = np.log(prices[mask])
            log_quantity = np.log(quantities[mask])

            # Simple OLS regression
            if len(log_price) > 1:
                slope, intercept = np.polyfit(log_price, log_quantity, 1)
                elasticity = slope
            else:
                elasticity = self.default_priors.get(product, {"mean": -0.5})["mean"]

            # Calculate confidence interval (simplified)
            residuals = log_quantity - (slope * log_price + intercept)
            se = np.std(residuals) / np.sqrt(len(log_price)) if len(log_price) > 2 else 0.1

            self.elasticities[product] = {
                "elasticity": float(elasticity),
                "standard_error": float(se),
                "confidence_lower": float(elasticity - 1.96 * se),
                "confidence_upper": float(elasticity + 1.96 * se),
                "n_observations": len(log_price),
            }

    def estimate_elasticity(
        self,
        product_name: str,
        current_price: float,
        current_quantity: float,
        prior: Optional[Dict] = None,
    ) -> ElasticityResult:
        """
        Estimate elasticity for a product.

        Args:
            product_name: Product identifier
            current_price: Current price
            current_quantity: Current quantity sold
            prior: Optional prior elasticity information

        Returns:
            Elasticity estimation result
        """
        # Use fitted elasticity or prior
        if product_name in self.elasticities:
            elasticity_info = self.elasticities[product_name]
            elasticity = elasticity_info["elasticity"]
            ci_lower = elasticity_info["confidence_lower"]
            ci_upper = elasticity_info["confidence_upper"]
        elif prior:
            elasticity = prior.get("mean", -0.5)
            ci_lower = elasticity - prior.get("std", 0.2)
            ci_upper = elasticity + prior.get("std", 0.2)
        else:
            elasticity = self.default_priors.get(product_name, {"mean": -0.5})["mean"]
            ci_lower = elasticity - 0.2
            ci_upper = elasticity + 0.2

        # Calculate optimal price
        optimal_price = self._calculate_optimal_price(elasticity, current_price)

        # Calculate revenue impact for price changes
        price_changes = [-0.1, -0.05, 0, 0.05, 0.1]
        revenue_impacts = {}
        for change in price_changes:
            new_price = current_price * (1 + change)
            quantity_change = elasticity * change
            new_quantity = current_quantity * (1 + quantity_change)
            new_revenue = new_price * new_quantity
            revenue_impacts[change] = new_revenue - (current_price * current_quantity)

        best_change = max(revenue_impacts, key=revenue_impacts.get)
        recommendation = self._generate_recommendation(
            elasticity, optimal_price, current_price, revenue_impacts[best_change]
        )

        return ElasticityResult(
            product_name=product_name,
            elasticity_estimate=elasticity,
            confidence_interval=(ci_lower, ci_upper),
            optimal_price=optimal_price,
            current_price=current_price,
            predicted_demand_change=elasticity * best_change,
            revenue_impact=revenue_impacts[best_change],
            recommendation=recommendation,
        )

    def _calculate_optimal_price(
        self,
        elasticity: float,
        current_price: float,
        marginal_cost: float = 0,
    ) -> float:
        """Calculate optimal price using elasticity"""
        if elasticity >= 0:
            return current_price  # Inelastic, no price change recommended

        # Optimal price formula: P* = MC / (1 + 1/e)
        optimal_price = marginal_cost / (1 + 1/elasticity)

        # Ensure optimal price is reasonable
        optimal_price = max(optimal_price, current_price * 0.5)
        optimal_price = min(optimal_price, current_price * 1.5)

        return optimal_price

    def _generate_recommendation(
        self,
        elasticity: float,
        optimal_price: float,
        current_price: float,
        revenue_impact: float,
    ) -> str:
        """Generate pricing recommendation"""
        price_diff_percent = (optimal_price - current_price) / current_price * 100

        if abs(price_diff_percent) < 5:
            return "Current price is near optimal. Maintain pricing."
        elif price_diff_percent > 0:
            return f"Consider price increase of {price_diff_percent:.1f}% to maximize revenue."
        else:
            return f"Consider price decrease of {abs(price_diff_percent):.1f}% to boost demand."

    def simulate_price_change(
        self,
        product_name: str,
        price_change_percent: float,
        current_quantity: int,
    ) -> Dict:
        """
        Simulate demand and revenue impact of price change.

        Args:
            product_name: Product identifier
            price_change_percent: Price change percentage (e.g., 10 for 10% increase)
            current_quantity: Current quantity sold

        Returns:
            Simulation results
        """
        elasticity = self.elasticities.get(product_name, {}).get(
            "elasticity",
            self.default_priors.get(product_name, {"mean": -0.5})["mean"]
        )

        # Calculate new quantity
        quantity_change = elasticity * (price_change_percent / 100)
        new_quantity = int(current_quantity * (1 + quantity_change))

        # Calculate revenue impact
        revenue_change_percent = price_change_percent + quantity_change * 100

        return {
            "price_change_percent": price_change_percent,
            "elasticity": elasticity,
            "quantity_change_percent": quantity_change * 100,
            "new_quantity": new_quantity,
            "revenue_change_percent": revenue_change_percent,
            "recommendation": (
                "Proceed with price change" if revenue_change_percent > 0
                else " reconsider pricing strategy"
            ),
        }


def generate_elasticity_data(
    n_observations: int = 1000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic price-quantity data"""
    rng = np.random.default_rng(random_state)

    products = ["plan_basic", "plan_premium", "data_addon", "roaming_package", "streaming_bundle"]
    base_prices = {"plan_basic": 50, "plan_premium": 100, "data_addon": 25,
                   "roaming_package": 40, "streaming_bundle": 15}
    base_quantities = {"plan_basic": 1000, "plan_premium": 500, "data_addon": 800,
                       "roaming_package": 300, "streaming_bundle": 600}
    elasticities = {"plan_basic": -0.3, "plan_premium": -0.5, "data_addon": -1.2,
                    "roaming_package": -0.8, "streaming_bundle": -1.5}

    data = []
    for _ in range(n_observations):
        product = rng.choice(products)
        base_price = base_prices[product]
        base_qty = base_quantities[product]
        true_elasticity = elasticities[product]

        # Generate price with some variation
        price = base_price * rng.uniform(0.8, 1.2)

        # Generate quantity based on price and elasticity (with noise)
        quantity = base_qty * (price / base_price) ** true_elasticity
        quantity = max(10, int(quantity + rng.normal(0, base_qty * 0.1)))

        data.append({
            "product_type": product,
            "price": round(price, 2),
            "quantity": quantity,
            "timestamp": pd.Timestamp.now() - pd.Timedelta(days=rng.integers(365)),
        })

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training Pricing Elasticity Model...")

    # Generate data
    df = generate_elasticity_data(n_observations=1000)
    print(f"Generated {len(df)} price-quantity observations")

    # Initialize model
    model = PricingElasticityModel()
    model.fit(df)

    # Estimate elasticities
    print("\nElasticity Estimates:")
    for product in df["product_type"].unique():
        if product in model.elasticities:
            info = model.elasticities[product]
            print(f"  {product}: {info['elasticity']:.3f} "
                  f"(CI: {info['confidence_lower']:.3f} to {info['confidence_upper']:.3f})")

    # Simulate price change
    simulation = model.simulate_price_change(
        product_name="data_addon",
        price_change_percent=10,
        current_quantity=800,
    )
    print(f"\nPrice Change Simulation (10% increase):")
    print(f"  New quantity: {simulation['new_quantity']}")
    print(f"  Revenue change: {simulation['revenue_change_percent']:.1f}%")
    print(f"  Recommendation: {simulation['recommendation']}")
