"""
Campaign Optimization Model

Optimizes marketing campaigns using:
- A/B test analysis
- Budget allocation
- Channel mix optimization
- Response rate prediction
- ROI maximization
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
from datetime import datetime


@dataclass
class CampaignResult:
    """Campaign optimization result"""
    campaign_id: str
    campaign_name: str
    total_budget: float
    allocated_budget: float
    predicted_revenue: float
    predicted_roi: float
    predicted_conversions: int
    channel_allocation: Dict[str, float]
    recommended_actions: List[str]
    risk_score: float


class CampaignOptimizer:
    """
    Marketing campaign optimization model.

    Optimizes:
    - Budget allocation across channels
    - Customer targeting
    - Offer selection
    - Timing optimization
    - Expected ROI maximization
    """

    def __init__(
        self,
        model_dir: str = "ml/propensity_model/campaign",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Channel performance baselines
        self.channel_baselines = {
            "sms": {"cost_per_contact": 0.01, "base_response_rate": 0.05},
            "email": {"cost_per_contact": 0.005, "base_response_rate": 0.03},
            "push_notification": {"cost_per_contact": 0.002, "base_response_rate": 0.08},
            "whatsapp": {"cost_per_contact": 0.02, "base_response_rate": 0.12},
            "phone_call": {"cost_per_contact": 0.50, "base_response_rate": 0.25},
            "personal_email": {"cost_per_contact": 0.01, "base_response_rate": 0.06},
        }

        # Offer performance baselines
        self.offer_baselines = {
            "discount_10pct": {" uplift_factor": 1.2, "cost": 10},
            "discount_20pct": {"uplift_factor": 1.5, "cost": 20},
            "free_data_5gb": {"uplift_factor": 1.3, "cost": 15},
            "free_month": {"uplift_factor": 1.8, "cost": 50},
            "loyalty_bonus": {"uplift_factor": 1.1, "cost": 5},
        }

    def optimize_campaign(
        self,
        total_budget: float,
        target_customers: int,
        propensity_data: pd.DataFrame,
        campaign_type: str = "retention",
    ) -> CampaignResult:
        """
        Optimize campaign budget allocation.

        Args:
            total_budget: Total campaign budget
            target_customers: Number of target customers
            propensity_data: Customer propensity scores
            campaign_type: Type of campaign (retention, acquisition, upsell)

        Returns:
            Campaign optimization result
        """
        # Calculate average propensity
        avg_propensity = propensity_data["probability"].mean() if "probability" in propensity_data.columns else 0.5

        # Determine channel mix based on campaign type
        channel_allocation = self._determine_channel_mix(campaign_type, total_budget)

        # Allocate budget across channels
        allocations = self._allocate_budget(channel_allocation, total_budget)

        # Calculate predicted metrics
        predicted_conversions = self._predict_conversions(
            target_customers, avg_propensity, allocations
        )
        predicted_revenue = predicted_conversions * self._get_average_order_value(campaign_type)
        predicted_roi = (predicted_revenue - total_budget) / total_budget * 100

        # Calculate risk score
        risk_score = self._calculate_risk(avg_propensity, target_customers)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            channel_allocation, allocations, avg_propensity
        )

        return CampaignResult(
            campaign_id=f"CAMP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            campaign_name=f"{campaign_type.capitalize()} Campaign",
            total_budget=total_budget,
            allocated_budget=sum(allocations.values()),
            predicted_revenue=predicted_revenue,
            predicted_roi=predicted_roi,
            predicted_conversions=predicted_conversions,
            channel_allocation=channel_allocation,
            recommended_actions=recommendations,
            risk_score=risk_score,
        )

    def _determine_channel_mix(
        self,
        campaign_type: str,
        budget: float,
    ) -> Dict[str, float]:
        """Determine optimal channel mix for campaign type"""
        mixes = {
            "retention": {
                "email": 0.3,
                "sms": 0.2,
                "push_notification": 0.2,
                "phone_call": 0.15,
                "whatsapp": 0.15,
            },
            "acquisition": {
                "sms": 0.25,
                "email": 0.25,
                "push_notification": 0.2,
                "whatsapp": 0.15,
                "personal_email": 0.15,
            },
            "upsell": {
                "phone_call": 0.3,
                "personal_email": 0.25,
                "email": 0.2,
                "whatsapp": 0.15,
                "sms": 0.1,
            },
        }

        return mixes.get(campaign_type, mixes["retention"])

    def _allocate_budget(
        self,
        channel_mix: Dict[str, float],
        total_budget: float,
    ) -> Dict[str, float]:
        """Allocate budget across channels"""
        allocations = {}
        remaining_budget = total_budget

        for channel, weight in channel_mix.items():
            cost_per_contact = self.channel_baselines.get(channel, {}).get("cost_per_contact", 0.01)
            allocation = total_budget * weight
            allocations[channel] = allocation
            remaining_budget -= allocation

        # Adjust last channel to use full budget
        if allocations:
            last_channel = list(channel_mix.keys())[-1]
            allocations[last_channel] += remaining_budget

        return allocations

    def _predict_conversions(
        self,
        n_customers: int,
        avg_propensity: float,
        allocations: Dict[str, float],
    ) -> int:
        """Predict number of conversions"""
        total_conversions = 0

        for channel, budget in allocations.items():
            channel_info = self.channel_baselines.get(channel, {})
            cost_per_contact = channel_info.get("cost_per_contact", 0.01)
            base_response = channel_info.get("base_response_rate", 0.05)

            # Calculate contacts reached
            n_contacts = budget / cost_per_contact
            n_contacts = min(n_contacts, n_customers)

            # Apply propensity adjustment
            response_rate = base_response * (0.5 + avg_propensity * 0.5)
            conversions = int(n_contacts * response_rate)

            total_conversions += conversions

        return min(total_conversions, n_customers)

    def _get_average_order_value(
        self,
        campaign_type: str,
    ) -> float:
        """Get average order value for campaign type"""
        values = {
            "retention": 50,
            "acquisition": 100,
            "upsell": 75,
        }
        return values.get(campaign_type, 50)

    def _calculate_risk(
        self,
        avg_propensity: float,
        n_customers: int,
    ) -> float:
        """Calculate campaign risk score (0-1, higher = riskier)"
        """
        # Risk factors
        low_propensity_risk = max(0, 0.5 - avg_propensity) * 0.5
        small_sample_risk = min(1, 1000 / max(n_customers, 1)) * 0.3
        budget_risk = min(1, 10000 / max(n_customers * 50, 1)) * 0.2

        return low_propensity_risk + small_sample_risk + budget_risk

    def _generate_recommendations(
        self,
        channel_mix: Dict[str, float],
        allocations: Dict[str, float],
        avg_propensity: float,
    ) -> List[str]:
        """Generate campaign recommendations"""
        recommendations = []

        # Channel recommendations
        best_channel = max(channel_mix, key=channel_mix.get)
        recommendations.append(
            f"Primary channel: {best_channel} ({channel_mix[best_channel]*100:.0f}% allocation)"
        )

        # Propensity-based recommendations
        if avg_propensity > 0.6:
            recommendations.append("High propensity segment - proceed with aggressive outreach")
        elif avg_propensity > 0.4:
            recommendations.append("Medium propensity - focus on high-value customers first")
        else:
            recommendations.append("Low propensity - consider re-engagement campaign first")

        # Budget recommendations
        if allocations.get(best_channel, 0) > allocations.get("phone_call", 0):
            recommendations.append("Consider adding phone call touchpoints for high-value segments")

        return recommendations

    def run_a_b_test_analysis(
        self,
        test_data: pd.DataFrame,
        control_col: str = "control_group",
        conversion_col: str = "converted",
    ) -> Dict:
        """
        Analyze A/B test results.

        Args:
            test_data: A/B test data
            control_col: Column indicating control group
            conversion_col: Column indicating conversion

        Returns:
            A/B test analysis results
        """
        # Split groups
        control = test_data[test_data[control_col] == 0]
        treatment = test_data[test_data[control_col] == 1]

        # Calculate metrics
        control_rate = control[conversion_col].mean()
        treatment_rate = treatment[conversion_col].mean()

        # Calculate lift
        lift = (treatment_rate - control_rate) / control_rate * 100 if control_rate > 0 else 0

        # Calculate statistical significance (simplified)
        n_control = len(control)
        n_treatment = len(treatment)
        pooled_rate = (control[conversion_col].sum() + treatment[conversion_col].sum()) / \
                      (n_control + n_treatment)

        se = np.sqrt(
            pooled_rate * (1 - pooled_rate) * (1/n_control + 1/n_treatment)
        )
        z_score = (treatment_rate - control_rate) / se if se > 0 else 0
        significant = abs(z_score) > 1.96  # 95% confidence

        return {
            "control_conversion_rate": control_rate,
            "treatment_conversion_rate": treatment_rate,
            "lift_percent": lift,
            "z_score": z_score,
            "statistically_significant": significant,
            "control_sample_size": n_control,
            "treatment_sample_size": n_treatment,
            "recommendation": "Implement treatment" if significant and lift > 0 else "Continue testing",
        }


def generate_campaign_data(
    n_customers: int = 10000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic campaign data"""
    rng = np.random.default_rng(random_state)

    data = {
        "customer_id": [f"CUST_{i:06d}" for i in range(n_customers)],
        "probability": rng.beta(2, 5, n_customers),
        "monthly_arpu": rng.lognormal(4.5, 0.5, n_customers),
        "age_group": rng.choice([0, 1, 2, 3, 4], n_customers),
        "device_type": rng.choice([0, 1, 2], n_customers, p=[0.3, 0.5, 0.2]),
        "channel_preference": rng.choice(
            ["sms", "email", "push", "whatsapp", "phone"],
            n_customers,
            p=[0.2, 0.2, 0.25, 0.2, 0.15]
        ),
        "last_contact_date": pd.date_range(
            "2024-01-01", periods=n_customers, freq="H"
        ),
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training Campaign Optimization Model...")

    # Generate data
    df = generate_campaign_data(n_customers=10000)
    print(f"Generated {len(df)} customer records")

    # Initialize optimizer
    optimizer = CampaignOptimizer()

    # Optimize retention campaign
    result = optimizer.optimize_campaign(
        total_budget=50000,
        target_customers=5000,
        propensity_data=df,
        campaign_type="retention",
    )

    print(f"\nCampaign Result:")
    print(f"  Budget: ${result.total_budget:,.2f}")
    print(f"  Predicted Revenue: ${result.predicted_revenue:,.2f}")
    print(f"  Predicted ROI: {result.predicted_roi:.1f}%")
    print(f"  Predicted Conversions: {result.predicted_conversions}")
    print(f"  Risk Score: {result.risk_score:.2f}")

    print(f"\nChannel Allocation:")
    for channel, pct in result.channel_allocation.items():
        print(f"  {channel}: {pct*100:.1f}%")

    print(f"\nRecommendations:")
    for rec in result.recommended_actions:
        print(f"  - {rec}")
