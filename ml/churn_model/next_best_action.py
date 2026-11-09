"""
Next Best Action (NBA) Recommendation System

Recommends optimal actions for each customer based on:
- Churn risk
- Customer segment
- Historical responses
- Available offers
- Expected value of each action
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class ActionType(Enum):
    """Available action types"""
    RETENTION_OFFER = "retention_offer"
    UPGRADE_PLAN = "upgrade_plan"
    CROSSSELL_DATA = "crosssell_data"
    CROSSSELL_ROAMING = "crosssell_roaming"
    LOYALTY_POINTS = "loyalty_points"
    SUPPORT_OUTREACH = "support_outreach"
    WINBACK = "winback"
    NO_ACTION = "no_action"


@dataclass
class NBARecommendation:
    """Next Best Action recommendation"""
    customer_id: str
    recommended_action: ActionType
    confidence: float
    expected_value: float
    reasoning: str
    alternatives: List[Dict]
    priority: int


class NextBestActionEngine:
    """
    NBA recommendation engine.

    Uses rules-based and ML-based approaches:
    - Rule-based for interpretability
    - ML-based for personalization
    - Expected value optimization
    - Constraint handling (budget, eligibility)
    """

    def __init__(
        self,
        model_dir: str = "ml/churn_model/nba",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Action configurations
        self.action_configs = {
            ActionType.RETENTION_OFFER: {
                "name": "Retention Offer",
                "description": "Special discount to prevent churn",
                "avg_value": 50,
                "cost": 30,
                "eligibility": ["high_churn_risk"],
            },
            ActionType.UPGRADE_PLAN: {
                "name": "Plan Upgrade",
                "description": "Upgrade to premium plan",
                "avg_value": 100,
                "cost": 10,
                "eligibility": ["medium_arpu", "high_usage"],
            },
            ActionType.CROSSSELL_DATA: {
                "name": "Data Add-on",
                "description": "Additional data bundle",
                "avg_value": 25,
                "cost": 5,
                "eligibility": ["high_data_usage"],
            },
            ActionType.CROSSSELL_ROAMING: {
                "name": "Roaming Package",
                "description": "International roaming package",
                "avg_value": 40,
                "cost": 8,
                "eligibility": ["roaming_customer"],
            },
            ActionType.LOYALTY_POINTS: {
                "name": "Loyalty Bonus",
                "description": "Extra loyalty points",
                "avg_value": 20,
                "cost": 15,
                "eligibility": ["high_tenure"],
            },
            ActionType.SUPPORT_OUTREACH: {
                "name": "Proactive Support",
                "description": "Contact customer before they churn",
                "avg_value": 75,
                "cost": 50,
                "eligibility": ["high_complaints", "high_risk"],
            },
            ActionType.WINBACK: {
                "name": "Win-back Campaign",
                "description": "Re-engage lost customer",
                "avg_value": 150,
                "cost": 40,
                "eligibility": ["churned"],
            },
            ActionType.NO_ACTION: {
                "name": "No Action",
                "description": "No intervention needed",
                "avg_value": 0,
                "cost": 0,
                "eligibility": [],
            },
        }

    def recommend(
        self,
        customer_data: pd.DataFrame,
        churn_probabilities: Optional[Dict[str, float]] = None,
        segments: Optional[Dict[str, str]] = None,
        budget_constraint: Optional[float] = None,
    ) -> List[NBARecommendation]:
        """
        Generate NBA recommendations for customers.

        Args:
            customer_data: Customer features
            churn_probabilities: Dict of customer_id -> churn probability
            segments: Dict of customer_id -> segment name
            budget_constraint: Maximum campaign budget

        Returns:
            List of NBARecommendation objects
        """
        recommendations = []

        for idx, row in customer_data.iterrows():
            customer_id = row.get("customer_id", f"CUST_{idx:06d}")

            # Get customer attributes
            churn_prob = churn_probabilities.get(customer_id, 0) if churn_probabilities else 0
            segment = segments.get(customer_id, "unknown") if segments else "unknown"
            arpu = row.get("monthly_arpu", 100)
            usage = row.get("data_usage_gb", 10)
            complaints = row.get("complaint_count_3m", 0)
            tenure = row.get("customer_tenure_months", 12)
            is_churned = row.get("is_churned", 0)

            # Evaluate each action
            action_scores = []
            for action, config in self.action_configs.items():
                if action == ActionType.NO_ACTION:
                    continue

                # Check eligibility
                eligible = True
                if "high_churn_risk" in config["eligibility"] and churn_prob < 0.5:
                    eligible = False
                if "medium_arpu" in config["eligibility"] and arpu < 100:
                    eligible = False
                if "high_usage" in config["eligibility"] and usage < 20:
                    eligible = False
                if "high_data_usage" in config["eligibility"] and usage < 30:
                    eligible = False
                if "roaming_customer" in config["eligibility"] and row.get("roaming_minutes", 0) < 10:
                    eligible = False
                if "high_tenure" in config["eligibility"] and tenure < 12:
                    eligible = False
                if "high_complaints" in config["eligibility"] and complaints < 2:
                    eligible = False
                if "high_risk" in config["eligibility"] and churn_prob < 0.4:
                    eligible = False
                if "churned" in config["eligibility"] and not is_churned:
                    eligible = False

                if not eligible:
                    action_scores.append((action, 0, 0))
                    continue

                # Calculate expected value
                base_value = config["avg_value"]
                cost = config["cost"]

                # Adjust based on customer attributes
                if action == ActionType.RETENTION_OFFER:
                    value_adjustment = churn_prob * 1.5  # Higher value for higher risk
                elif action == ActionType.UPGRADE_PLAN:
                    value_adjustment = (arpu / 150) * 0.5  # Based on ARPU
                elif action == ActionType.SUPPORT_OUTREACH:
                    value_adjustment = complaints * 0.3 + churn_prob * 0.7
                else:
                    value_adjustment = 1.0

                expected_value = base_value * value_adjustment - cost
                confidence = min(0.95, 0.5 + value_adjustment * 0.3)

                action_scores.append((action, expected_value, confidence))

            # Sort by expected value
            action_scores.sort(key=lambda x: x[1], reverse=True)

            # Select best action
            if action_scores and action_scores[0][1] > 0:
                best_action, best_value, best_confidence = action_scores[0]
                reasoning = self._generate_reasoning(best_action, customer_id, row)
            else:
                best_action = ActionType.NO_ACTION
                best_value = 0
                best_confidence = 0.5
                reasoning = "No suitable action identified"

            # Get alternatives
            alternatives = [
                {
                    "action": action.value,
                    "expected_value": value,
                    "confidence": confidence,
                }
                for action, value, confidence in action_scores[:3]
            ]

            # Determine priority
            priority = self._calculate_priority(best_action, best_value, best_confidence)

            recommendations.append(NBARecommendation(
                customer_id=customer_id,
                recommended_action=best_action,
                confidence=best_confidence,
                expected_value=best_value,
                reasoning=reasoning,
                alternatives=alternatives,
                priority=priority,
            ))

        # Apply budget constraint if specified
        if budget_constraint is not None:
            recommendations = self._apply_budget_constraint(
                recommendations, budget_constraint
            )

        # Sort by priority
        recommendations.sort(key=lambda x: x.priority)

        return recommendations

    def _generate_reasoning(
        self,
        action: ActionType,
        customer_id: str,
        customer_data: pd.Series,
    ) -> str:
        """Generate human-readable reasoning for recommendation"""
        reasons = {
            ActionType.RETENTION_OFFER: f"High churn risk ({customer_data.get('churn_prob', 0):.0%}) detected. Retention offer recommended.",
            ActionType.UPGRADE_PLAN: f"High usage customer ({customer_data.get('data_usage_gb', 0):.1f} GB). Plan upgrade opportunity.",
            ActionType.CROSSSELL_DATA: f"Heavy data user ({customer_data.get('data_usage_gb', 0):.1f} GB). Data add-on recommended.",
            ActionType.CROSSSELL_ROAMING: f"Active roaming user ({customer_data.get('roaming_minutes', 0):.0f} min). Roaming package recommended.",
            ActionType.LOYALTY_POINTS: f"Loyal customer ({customer_data.get('customer_tenure_months', 0):.0f} months). Loyalty bonus to maintain engagement.",
            ActionType.SUPPORT_OUTREACH: f"Customer with {customer_data.get('complaint_count_3m', 0)} complaints. Proactive support needed.",
            ActionType.WINBACK: f"Former customer eligible for win-back campaign.",
            ActionType.NO_ACTION: "Customer is healthy, no intervention needed.",
        }
        return reasons.get(action, "Recommendation generated by NBA engine.")

    def _calculate_priority(
        self,
        action: ActionType,
        expected_value: float,
        confidence: float,
    ) -> int:
        """Calculate action priority (lower = higher priority)"""
        # Base priority from action type
        base_priorities = {
            ActionType.RETENTION_OFFER: 1,
            ActionType.SUPPORT_OUTREACH: 2,
            ActionType.UPGRADE_PLAN: 3,
            ActionType.WINBACK: 4,
            ActionType.CROSSSELL_DATA: 5,
            ActionType.CROSSSELL_ROAMING: 6,
            ActionType.LOYALTY_POINTS: 7,
            ActionType.NO_ACTION: 10,
        }

        priority = base_priorities.get(action, 5)

        # Adjust by expected value and confidence
        if expected_value > 100 and confidence > 0.7:
            priority -= 1

        return max(1, priority)

    def _apply_budget_constraint(
        self,
        recommendations: List[NBARecommendation],
        budget: float,
    ) -> List[NBARecommendation]:
        """Apply budget constraint to recommendations"""
        total_cost = sum(
            self.action_configs[r.recommended_action]["cost"]
            for r in recommendations
        )

        if total_cost <= budget:
            return recommendations

        # Scale down by budget ratio
        scale_factor = budget / total_cost
        np.random.seed(42)
        mask = np.random.random(len(recommendations)) < scale_factor

        return [r for i, r in enumerate(recommendations) if mask[i]]

    def calculate_campaign_metrics(
        self,
        recommendations: List[NBARecommendation],
    ) -> Dict:
        """Calculate aggregate campaign metrics"""
        total_expected_value = sum(r.expected_value for r in recommendations)
        total_cost = sum(
            self.action_configs[r.recommended_action]["cost"]
            for r in recommendations
        )

        action_counts = {}
        for r in recommendations:
            action = r.recommended_action.value
            action_counts[action] = action_counts.get(action, 0) + 1

        return {
            "total_customers": len(recommendations),
            "total_expected_value": total_expected_value,
            "total_cost": total_cost,
            "net_value": total_expected_value - total_cost,
            "roi_percent": ((total_expected_value - total_cost) / total_cost * 100) if total_cost > 0 else 0,
            "action_distribution": action_counts,
            "avg_confidence": np.mean([r.confidence for r in recommendations]),
        }


def generate_nba_data(
    n_samples: int = 1000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic data for NBA recommendations"""
    rng = np.random.default_rng(random_state)

    data = {
        "customer_id": [f"CUST_{i:06d}" for i in range(n_samples)],
        "monthly_arpu": rng.lognormal(4.5, 0.5, n_samples).clip(50, 500),
        "data_usage_gb": rng.lognormal(2.5, 0.8, n_samples).clip(1, 100),
        "complaint_count_3m": rng.poisson(1, n_samples),
        "customer_tenure_months": rng.exponential(24, n_samples).clip(1, 120),
        "roaming_minutes": rng.exponential(30, n_samples).clip(0, 500),
        "churn_prob": rng.beta(2, 5, n_samples),  # Skewed towards low churn
        "is_churned": rng.choice([0, 1], n_samples, p=[0.9, 0.1]),
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training NBA Recommendation Engine...")

    # Generate data
    df = generate_nba_data(n_samples=1000)
    print(f"Generated {len(df)} customer records")

    # Initialize engine
    nba_engine = NextBestActionEngine()

    # Get churn probabilities (in production, from churn model)
    churn_probs = {
        row["customer_id"]: row["churn_prob"]
        for _, row in df.iterrows()
    }

    # Generate recommendations
    recommendations = nba_engine.recommend(
        df,
        churn_probabilities=churn_probs,
        budget_constraint=50000,
    )

    # Print results
    print(f"\nGenerated {len(recommendations)} recommendations")
    for rec in recommendations[:5]:
        print(f"  {rec.customer_id}: {rec.recommended_action.value} "
              f"(value=${rec.expected_value:.2f}, conf={rec.confidence:.2f})")

    # Campaign metrics
    metrics = nba_engine.calculate_campaign_metrics(recommendations)
    print(f"\nCampaign Metrics:")
    print(f"  Total Expected Value: ${metrics['total_expected_value']:.2f}")
    print(f"  Total Cost: ${metrics['total_cost']:.2f}")
    print(f"  ROI: {metrics['roi_percent']:.1f}%")
