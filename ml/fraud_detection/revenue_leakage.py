"""
Revenue Leakage Detection Model

Identifies revenue leakage sources:
- Unbilled usage
- Incorrect rating
- Discount abuse
- Partner settlement discrepancies
- CDR gaps and duplications
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class LeakageType(Enum):
    """Revenue leakage types"""
    UNBILLED_USAGE = "unbilled_usage"
    INCORRECT_RATING = "incorrect_rating"
    DISCOUNT_ABUSE = "discount_abuse"
    PARTNER_SETTLEMENT = "partner_settlement"
    CDR_GAP = "cdr_gap"
    CDR_DUPLICATION = "cdr_duplication"
    PLAN_MISMATCH = "plan_mismatch"
    FREE_TIER_ABUSE = "free_tier_abuse"


@dataclass
class LeakageDetection:
    """Revenue leakage detection result"""
    leakage_id: str
    leakage_type: LeakageType
    estimated_loss: float
    confidence: float
    affected_customers: int
    root_cause: str
    recommendation: str
    severity: str
    timestamp: str


class RevenueLeakageDetector:
    """
    Revenue leakage detection system.

    Detects leakage through:
    - CDR analysis (gaps, duplications)
    - Rating rule validation
    - Discount pattern analysis
    - Partner settlement reconciliation
    - Plan-billing consistency checks
    """

    def __init__(
        self,
        model_dir: str = "ml/fraud_detection/leakage",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Leakage detection thresholds
        self.thresholds = {
            "cdr_gap_minutes": 5,
            "duplication_threshold": 0.95,
            "rating_variance_threshold": 0.1,
            "discount_abuse_threshold": 0.5,
            "settlement_variance_threshold": 0.05,
        }

    def detect_cdr_gaps(
        self,
        cdr_data: pd.DataFrame,
        customer_id_col: str = "customer_id",
        timestamp_col: str = "start_time",
        duration_col: str = "duration_seconds",
    ) -> List[LeakageDetection]:
        """Detect unbilled usage due to CDR gaps"""
        detections = []

        # Sort by customer and time
        cdr_sorted = cdr_data.sort_values([customer_id_col, timestamp_col])

        # Find gaps in CDRs for each customer
        for customer_id, group in cdr_sorted.groupby(customer_id_col):
            group = group.sort_values(timestamp_col)

            for i in range(1, len(group)):
                prev_row = group.iloc[i - 1]
                curr_row = group.iloc[i]

                time_diff = (curr_row[timestamp_col] - prev_row[timestamp_col]) / pd.Timedelta(minutes=1)
                actual_duration = prev_row[duration_col] / 60

                # Check for gap larger than expected
                gap = time_diff - actual_duration
                if gap > self.thresholds["cdr_gap_minutes"]:
                    estimated_loss = gap * 0.05  # Simplified rate calculation

                    detections.append(LeakageDetection(
                        leakage_id=f"LEAK_CDR_{customer_id}_{i}",
                        leakage_type=LeakageType.CDR_GAP,
                        estimated_loss=estimated_loss,
                        confidence=0.85,
                        affected_customers=1,
                        root_cause=f"CDR gap of {gap:.1f} minutes detected",
                        recommendation="Investigate CDR collection system for missing records",
                        severity="high",
                        timestamp=pd.Timestamp.now().isoformat(),
                    ))

        return detections

    def detect_cdr_duplications(
        self,
        cdr_data: pd.DataFrame,
        similarity_threshold: float = None,
    ) -> List[LeakageDetection]:
        """Detect duplicate CDRs causing overbilling"""
        if similarity_threshold is None:
            similarity_threshold = self.thresholds["duplication_threshold"]

        detections = []

        # Simplified duplication detection
        # In production, would use more sophisticated matching
        duplicate_flags = cdr_data.duplicated(
            subset=["customer_id", "start_time", "duration_seconds", "end_number"],
            keep=False
        )

        n_duplicates = duplicate_flags.sum() // 2  # Each pair counted twice
        if n_duplicates > 0:
            estimated_loss = n_duplicates * 50  # Average call cost

            detections.append(LeakageDetection(
                leakage_id="LEAK_DUP_GLOBAL",
                leakage_type=LeakageType.CDR_DUPLICATION,
                estimated_loss=estimated_loss,
                confidence=0.9,
                affected_customers=n_duplicates,
                root_cause=f"{n_duplicates} duplicate CDR pairs detected",
                recommendation="Implement CDR deduplication in billing system",
                severity="critical",
                timestamp=pd.Timestamp.now().isoformat(),
            ))

        return detections

    def detect_rating_issues(
        self,
        billing_data: pd.DataFrame,
        expected_rate_col: str = "expected_rate",
        actual_rate_col: str = "actual_rate",
    ) -> List[LeakageDetection]:
        """Detect incorrect rating causing revenue leakage"""
        detections = []

        variance = abs(
            billing_data[actual_rate_col] - billing_data[expected_rate_col]
        ) / billing_data[expected_rate_col]

        high_variance = variance > self.thresholds["rating_variance_threshold"]
        n_affected = high_variance.sum()

        if n_affected > 0:
            estimated_loss = (billing_data[high_variance][actual_rate_col] -
                             billing_data[high_variance][expected_rate_col]).sum()

            detections.append(LeakageDetection(
                leakage_id="LEAK_RATE_GLOBAL",
                leakage_type=LeakageType.INCORRECT_RATING,
                estimated_loss=max(0, estimated_loss),
                confidence=0.8,
                affected_customers=n_affected,
                root_cause=f"{n_affected} billing records with rate variance > 10%",
                recommendation="Review rating rules and tariff configurations",
                severity="high" if n_affected > 100 else "medium",
                timestamp=pd.Timestamp.now().isoformat(),
            ))

        return detections

    def detect_discount_abuse(
        self,
        billing_data: pd.DataFrame,
        discount_col: str = "discount_percentage",
        arpu_col: str = "monthly_charge",
    ) -> List[LeakageDetection]:
        """Detect excessive discount usage"""
        detections = []

        # Find customers with unusually high discounts
        high_discounts = billing_data[billing_data[discount_col] >
                                     self.thresholds["discount_abuse_threshold"] * 100]

        if len(high_discounts) > 0:
            estimated_loss = (high_discounts[arpu_col] * high_discounts[discount_col] / 100).sum()

            detections.append(LeakageDetection(
                leakage_id="LEAK_DISCOUNT_GLOBAL",
                leakage_type=LeakageType.DISCOUNT_ABUSE,
                estimated_loss=estimated_loss,
                confidence=0.75,
                affected_customers=len(high_discounts),
                root_cause=f"{len(high_discounts)} customers with discount > 50%",
                recommendation="Review discount approval process and thresholds",
                severity="medium",
                timestamp=pd.Timestamp.now().isoformat(),
            ))

        return detections

    def detect_partner_settlement_issues(
        self,
        partner_data: pd.DataFrame,
        billed_col: str = "billed_amount",
        settled_col: str = "settled_amount",
    ) -> List[LeakageDetection]:
        """Detect partner settlement discrepancies"""
        detections = []

        variance = abs(
            partner_data[billed_col] - partner_data[settled_col]
        ) / partner_data[billed_col]

        high_variance = variance > self.thresholds["settlement_variance_threshold"]
        n_affected = high_variance.sum()

        if n_affected > 0:
            estimated_loss = (partner_data[high_variance][billed_col] -
                             partner_data[high_variance][settled_col]).sum()

            detections.append(LeakageDetection(
                leakage_id="LEAK_PARTNER_GLOBAL",
                leakage_type=LeakageType.PARTNER_SETTLEMENT,
                estimated_loss=max(0, estimated_loss),
                confidence=0.85,
                affected_customers=n_affected,
                root_cause=f"{n_affected} partner settlements with > 5% variance",
                recommendation="Reconcile partner billing systems and update agreements",
                severity="high" if n_affected > 5 else "medium",
                timestamp=pd.Timestamp.now().isoformat(),
            ))

        return detections

    def run_full_detection(
        self,
        cdr_data: Optional[pd.DataFrame] = None,
        billing_data: Optional[pd.DataFrame] = None,
        partner_data: Optional[pd.DataFrame] = None,
    ) -> Dict:
        """Run all leakage detection methods"""
        all_detections = []

        if cdr_data is not None:
            all_detections.extend(self.detect_cdr_gaps(cdr_data))
            all_detections.extend(self.detect_cdr_duplications(cdr_data))

        if billing_data is not None:
            all_detections.extend(self.detect_rating_issues(billing_data))
            all_detections.extend(self.detect_discount_abuse(billing_data))

        if partner_data is not None:
            all_detections.extend(self.detect_partner_settlement_issues(partner_data))

        # Aggregate summary
        total_loss = sum(d.estimated_loss for d in all_detections)
        by_type = {}
        for d in all_detections:
            type_key = d.leakage_type.value
            by_type[type_key] = by_type.get(type_key, 0) + d.estimated_loss

        return {
            "total_detections": len(all_detections),
            "total_estimated_loss": total_loss,
            "by_type": by_type,
            "detections": [
                {
                    "leakage_id": d.leakage_id,
                    "leakage_type": d.leakage_type.value,
                    "estimated_loss": d.estimated_loss,
                    "confidence": d.confidence,
                    "severity": d.severity,
                    "root_cause": d.root_cause,
                    "recommendation": d.recommendation,
                }
                for d in all_detections
            ],
        }


def generate_leakage_data(
    n_cdr: int = 100000,
    n_billing: int = 10000,
    n_partners: int = 20,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic data for leakage detection"""
    rng = np.random.default_rng(random_state)

    # CDR data with some gaps and duplications
    cdr_data = pd.DataFrame({
        "customer_id": [f"CUST_{i:06d}" for i in rng.choice(range(10000), n_cdr, replace=True)],
        "start_time": pd.date_range("2024-01-01", periods=n_cdr, freq="min"),
        "duration_seconds": rng.exponential(180, n_cdr),
        "end_number": [f"+9665{i:06d}" for i in rng.choice(range(100000), n_cdr)],
        "call_type": rng.choice(["local", "national", "international"], n_cdr, p=[0.7, 0.2, 0.1]),
    })

    # Add some duplications
    dup_indices = rng.choice(n_cdr, size=n_cdr // 100, replace=False)
    cdr_data = pd.concat([cdr_data, cdr_data.iloc[dup_indices]], ignore_index=True)

    # Billing data with some rating issues
    billing_data = pd.DataFrame({
        "customer_id": [f"CUST_{i:06d}" for i in range(n_billing)],
        "expected_rate": rng.uniform(0.05, 0.5, n_billing),
        "actual_rate": rng.normal(0.25, 0.05, n_billing),
        "discount_percentage": rng.exponential(10, n_billing),
        "monthly_charge": rng.lognormal(4.5, 0.5, n_billing),
    })

    # Add some high discounts
    high_discount_idx = rng.choice(n_billing, size=n_billing // 20, replace=False)
    billing_data.loc[high_discount_idx, "discount_percentage"] = rng.uniform(50, 80, len(high_discount_idx))

    # Partner settlement data
    partner_data = pd.DataFrame({
        "partner_id": [f"PARTNER_{i:03d}" for i in range(n_partners)],
        "billed_amount": rng.uniform(10000, 100000, n_partners),
        "settled_amount": rng.normal(95000, 5000, n_partners),
    })

    return cdr_data, billing_data, partner_data


if __name__ == "__main__":
    # Example usage
    print("Training Revenue Leakage Detection Model...")

    # Generate data
    cdr_data, billing_data, partner_data = generate_leakage_data()
    print(f"Generated CDR: {len(cdr_data)}, Billing: {len(billing_data)}, Partners: {len(partner_data)}")

    # Initialize detector
    detector = RevenueLeakageDetector()

    # Run full detection
    results = detector.run_full_detection(
        cdr_data=cdr_data,
        billing_data=billing_data,
        partner_data=partner_data,
    )

    print(f"\nTotal Estimated Loss: ${results['total_estimated_loss']:,.2f}")
    print(f"Total Detections: {results['total_detections']}")
    print(f"\nLeakage by Type:")
    for leak_type, loss in results["by_type"].items():
        print(f"  {leak_type}: ${loss:,.2f}")

    print(f"\nDetections:")
    for det in results["detections"]:
        print(f"  [{det['severity'].upper()}] {det['leakage_type']}: ${det['estimated_loss']:,.2f}")
