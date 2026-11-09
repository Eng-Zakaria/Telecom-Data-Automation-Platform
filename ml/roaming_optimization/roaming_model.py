"""
Roaming & Settlement Optimization Models

Provides machine learning models for:
- Roaming partner selection optimization
- Settlement discrepancy detection
- Revenue optimization per partner
- Fraud pattern detection in roaming
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from datetime import datetime


class SettlementIssue(Enum):
    """Settlement issue types"""
    MISSING_CDR = "missing_cdr"
    DUPLICATE_CDR = "duplicate_cdr"
    RATE_DISCREPANCY = "rate_discrepancy"
    QUALITY_DEGRADATION = "quality_degradation"
    FRAUD_PATTERN = "fraud_pattern"
    CONTRACT_VIOLATION = "contract_violation"


@dataclass
class PartnerPerformance:
    """Roaming partner performance metrics"""
    partner_id: str
    partner_name: str
    total_roaming_minutes: int
    total_revenue: float
    total_cost: float
    settlement_variance: float
    fraud_score: float
    quality_score: float
    reliability_score: float
    overall_score: float
    recommendation: str


class RoamingOptimizationModel:
    """
    Roaming and partner settlement optimization model.

    Optimizes:
    - Partner selection based on cost/quality
    - Settlement reconciliation
    - Fraud detection in roaming
    - Revenue optimization
    """

    def __init__(
        self,
        model_dir: str = "ml/roaming_optimization",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Partner performance tracking
        self.partner_metrics = {}
        self.settlement_history = []

        # Fraud detection thresholds
        self.fraud_thresholds = {
            "high_roaming_minutes": 500,
            "sudden_spike": 2.0,  # 2x normal
            "odd_hours": 0.3,  # 30% odd hour activity
            "geographic_impossibility": 0.5,
        }

    def analyze_partner_performance(
        self,
        df: pd.DataFrame,
        partner_id_col: str = "partner_id",
        minutes_col: str = "roaming_minutes",
        revenue_col: str = "revenue",
        cost_col: str = "settlement_cost",
    ) -> List[PartnerPerformance]:
        """
        Analyze roaming partner performance.

        Args:
            df: Partner performance data
            partner_id_col: Column name for partner ID
            minutes_col: Column name for roaming minutes
            revenue_col: Column name for revenue
            cost_col: Column name for settlement cost

        Returns:
            List of PartnerPerformance objects
        """
        performances = []

        for partner_id, group in df.groupby(partner_id_col):
            total_minutes = group[minutes_col].sum()
            total_revenue = group[revenue_col].sum()
            total_cost = group[cost_col].sum()

            # Calculate settlement variance
            settlement_variance = abs(total_revenue - total_cost) / total_revenue if total_revenue > 0 else 0

            # Calculate quality score (simplified)
            quality_score = self._calculate_quality_score(group)

            # Calculate fraud score
            fraud_score = self._calculate_fraud_score(group)

            # Calculate reliability score
            reliability_score = self._calculate_reliability_score(group)

            # Calculate overall score (weighted combination)
            overall_score = (
                quality_score * 0.3 +
                fraud_score * 0.2 +
                reliability_score * 0.2 +
                (1 - settlement_variance) * 0.3
            )

            # Generate recommendation
            recommendation = self._generate_partner_recommendation(
                overall_score, settlement_variance, fraud_score
            )

            partner_name = str(partner_id)
            if "partner_name" in group.columns:
                partner_name = str(group["partner_name"].iloc[0]) if len(group) > 0 else str(partner_id)

            performances.append(PartnerPerformance(
                partner_id=str(partner_id),
                partner_name=partner_name,
                total_roaming_minutes=int(total_minutes),
                total_revenue=float(total_revenue),
                total_cost=float(total_cost),
                settlement_variance=float(settlement_variance),
                fraud_score=float(fraud_score),
                quality_score=float(quality_score),
                reliability_score=float(reliability_score),
                overall_score=float(overall_score),
                recommendation=recommendation,
            ))

        # Sort by overall score
        performances.sort(key=lambda x: x.overall_score, reverse=True)

        return performances

    def detect_settlement_issues(
        self,
        billed_df: pd.DataFrame,
        settled_df: pd.DataFrame,
        partner_id_col: str = "partner_id",
        amount_col: str = "amount",
        date_col: str = "date",
    ) -> List[Dict]:
        """
        Detect settlement discrepancies between billed and settled amounts.

        Args:
            billed_df: Billed amount data
            settled_df: Settled amount data
            partner_id_col: Column name for partner ID
            amount_col: Column name for amount
            date_col: Column name for date

        Returns:
            List of settlement issues
        """
        issues = []

        # Merge billed and settled data
        merged = pd.merge(
            billed_df[[partner_id_col, date_col, amount_col]].rename(columns={amount_col: "billed"}),
            settled_df[[partner_id_col, date_col, amount_col]].rename(columns={amount_col: "settled"}),
            on=[partner_id_col, date_col],
            how="outer"
        )

        # Calculate variance
        merged["billed"] = merged["billed"].fillna(0)
        merged["settled"] = merged["settled"].fillna(0)
        merged["variance"] = abs(merged["billed"] - merged["settled"])
        merged["variance_percent"] = merged["variance"] / (merged["billed"] + 1)

        # Identify issues
        for idx, row in merged.iterrows():
            if row["variance_percent"] > 0.05:  # 5% threshold
                issue_type = self._classify_settlement_issue(row)

                issues.append({
                    "partner_id": row[partner_id_col],
                    "date": row[date_col],
                    "billed": row["billed"],
                    "settled": row["settled"],
                    "variance": row["variance"],
                    "variance_percent": row["variance_percent"],
                    "issue_type": issue_type.value,
                    "severity": "high" if row["variance_percent"] > 0.1 else "medium",
                    "recommendation": self._get_issue_recommendation(issue_type, row["variance_percent"]),
                })

        return issues

    def optimize_roaming_routes(
        self,
        df: pd.DataFrame,
        origin_col: str = "origin_country",
        destination_col: str = "destination_country",
        cost_col: str = "roaming_cost",
        quality_col: str = "network_quality",
    ) -> Dict:
        """
        Optimize roaming route selection.

        Args:
            df: Roaming route data
            origin_col: Column name for origin country
            destination_col: Column name for destination country
            cost_col: Column name for roaming cost
            quality_col: Column name for network quality

        Returns:
            Route optimization recommendations
        """
        # Group by origin-destination pair
        routes = df.groupby([origin_col, destination_col]).agg({
            cost_col: "mean",
            quality_col: "mean",
        }).reset_index()

        # Calculate cost-quality ratio (lower is better)
        routes["cost_quality_ratio"] = routes[cost_col] / (routes[quality_col] + 0.01)

        # Find optimal routes for each destination
        optimal_routes = {}
        for dest in routes[destination_col].unique():
            dest_routes = routes[routes[destination_col] == dest].sort_values("cost_quality_ratio")

            if len(dest_routes) > 0:
                best_route = dest_routes.iloc[0]
                optimal_routes[f"{best_route[origin_col]}->{dest}"] = {
                    "origin": best_route[origin_col],
                    "destination": dest,
                    "cost": float(best_route[cost_col]),
                    "quality": float(best_route[quality_col]),
                    "cost_quality_ratio": float(best_route["cost_quality_ratio"]),
                    "recommendation": "Use this partner for cost optimization",
                }

        return optimal_routes

    def _calculate_quality_score(self, group: pd.DataFrame) -> float:
        """Calculate partner quality score"""
        # Simplified quality score based on network metrics
        if "signal_strength" in group.columns:
            return min(1.0, group["signal_strength"].mean() / -70)
        return 0.7  # Default quality score

    def _calculate_fraud_score(self, group: pd.DataFrame) -> float:
        """Calculate fraud risk score"""
        score = 0.0

        # Check for high roaming minutes
        if "roaming_minutes" in group.columns:
            high_roaming = (group["roaming_minutes"] > self.fraud_thresholds["high_roaming_minutes"]).mean()
            score += high_roaming * 0.3

        # Check for odd hour activity
        if "hour" in group.columns:
            odd_hours = ((group["hour"] < 6) | (group["hour"] > 23)).mean()
            score += min(1, odd_hours / self.fraud_thresholds["odd_hours"]) * 0.2

        return min(1.0, score)

    def _calculate_reliability_score(self, group: pd.DataFrame) -> float:
        """Calculate partner reliability score"""
        # Simplified reliability based on settlement consistency
        if "settlement_variance" in group.columns:
            return max(0, 1 - group["settlement_variance"].mean())
        return 0.8  # Default reliability

    def _classify_settlement_issue(self, row: pd.Series) -> SettlementIssue:
        """Classify settlement issue type"""
        if row["billed"] == 0 and row["settled"] > 0:
            return SettlementIssue.MISSING_CDR
        elif row["settled"] == 0 and row["billed"] > 0:
            return SettlementIssue.DUPLICATE_CDR
        elif row["variance_percent"] > 0.1:
            return SettlementIssue.RATE_DISCREPANCY
        else:
            return SettlementIssue.QUALITY_DEGRADATION

    def _get_issue_recommendation(self, issue_type: SettlementIssue, variance: float) -> str:
        """Get recommendation for settlement issue"""
        recommendations = {
            SettlementIssue.MISSING_CDR: "Investigate missing CDRs and implement CDR reconciliation",
            SettlementIssue.DUPLICATE_CDR: "Review billing system for duplicate entries",
            SettlementIssue.RATE_DISCREPANCY: "Verify rate cards and contract terms with partner",
            SettlementIssue.QUALITY_DEGRADATION: "Assess network quality and consider partner switching",
            SettlementIssue.FRAUD_PATTERN: "Escalate to fraud investigation team",
            SettlementIssue.CONTRACT_VIOLATION: "Review contract compliance and initiate remediation",
        }
        return recommendations.get(issue_type, "Review and reconcile billing data")

    def _generate_partner_recommendation(
        self,
        overall_score: float,
        settlement_variance: float,
        fraud_score: float,
    ) -> str:
        """Generate partner performance recommendation"""
        if overall_score >= 0.8 and fraud_score < 0.3:
            return "Excellent partner - maintain and expand relationship"
        elif overall_score >= 0.6 and fraud_score < 0.5:
            return "Good partner - monitor and optimize"
        elif settlement_variance > 0.1:
            return "High settlement variance - reconcile before continuing"
        elif fraud_score > 0.5:
            return "High fraud risk - implement additional controls"
        else:
            return "Consider alternative partners or renegotiate terms"


def generate_roaming_data(
    n_records: int = 10000,
    n_partners: int = 15,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic roaming data"""
    rng = np.random.default_rng(random_state)

    partners = [f"PARTNER_{i:03d}" for i in range(n_partners)]
    partner_names = {
        "PARTNER_001": "Stc International",
        "PARTNER_002": "Mobily Roaming",
        "PARTNER_003": "Intersat",
        "PARTNER_004": "Vodafone RO",
        "PARTNER_005": "Etisalat RO",
    }

    data = {
        "partner_id": rng.choice(partners, n_records),
        "customer_id": [f"CUST_{i:06d}" for i in rng.choice(range(5000), n_records)],
        "roaming_minutes": rng.exponential(30, n_records),
        "revenue": rng.lognormal(4, 0.5, n_records),
        "settlement_cost": rng.lognormal(3.8, 0.5, n_records),
        "origin_country": rng.choice(["SA", "AE", "KW", "QA", "BH"], n_records),
        "destination_country": rng.choice(["UK", "US", "DE", "FR", "IN"], n_records),
        "network_quality": rng.beta(5, 2, n_records),
        "signal_strength": rng.normal(-80, 10, n_records),
        "hour": rng.integers(24, n_records),
        "call_type": rng.choice(["voice", "data", "sms"], n_records, p=[0.5, 0.4, 0.1]),
    }

    df = pd.DataFrame(data)

    # Add partner names
    df["partner_name"] = df["partner_id"].map(partner_names).fillna(df["partner_id"])

    # Add some fraud patterns
    fraud_indices = rng.choice(n_records, size=n_records // 20, replace=False)
    df.loc[fraud_indices, "roaming_minutes"] *= 5
    df.loc[fraud_indices, "hour"] = rng.choice([1, 2, 3, 4, 5, 22, 23], len(fraud_indices))

    return df


if __name__ == "__main__":
    # Example usage
    print("Training Roaming Optimization Model...")

    # Generate data
    df = generate_roaming_data(n_records=10000, n_partners=15)
    print(f"Generated {len(df)} roaming records")

    # Initialize model
    model = RoamingOptimizationModel()

    # Analyze partner performance
    performances = model.analyze_partner_performance(df)
    print(f"\nPartner Performance Analysis:")
    for perf in performances[:5]:
        print(f"  {perf.partner_id}: Score={perf.overall_score:.2f}, "
              f"Revenue=${perf.total_revenue:.2f}, Fraud={perf.fraud_score:.2f}")
        print(f"    Recommendation: {perf.recommendation}")

    # Optimize roaming routes
    routes = model.optimize_roaming_routes(df)
    print(f"\nOptimal Routes:")
    for route, info in list(routes.items())[:5]:
        print(f"  {route}: Cost=${info['cost']:.2f}, Quality={info['quality']:.2f}")
