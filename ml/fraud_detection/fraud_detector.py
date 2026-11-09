"""
Fraud Detection Model

Detects telecom fraud patterns using:
- Isolation Forest for anomaly detection
- Rule-based fraud pattern detection
- Real-time scoring with explainability
- Multi-layer fraud detection (SIM-box, roaming, revenue leak)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Using fallback implementation.")


class FraudType(Enum):
    """Fraud pattern types"""
    SIM_BOX = "sim_box"
    ROAMING_FRAUD = "roaming_fraud"
    REVENUE_LEAKAGE = "revenue_leakage"
    SUBSCRIPTION_FRAUD = "subscription_fraud"
    INTERNATIONAL_REVENUE_SHARE_FRAUD = "irs_fraud"
    CALL_FORWARDING_FRAUD = "call_forwarding_fraud"
    CDR_FABRICATION = "cdr_fabrication"


class FraudSeverity(Enum):
    """Fraud severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class FraudDetection:
    """Fraud detection result"""
    transaction_id: str
    customer_id: str
    fraud_type: FraudType
    fraud_score: float
    severity: FraudSeverity
    confidence: float
    rules_triggered: List[str]
    features_contributing: List[Tuple[str, float]]
    recommendation: str
    timestamp: str


class FeatureEngineer:
    """Feature engineering for fraud detection"""

    def __init__(self):
        self.feature_names = [
            # CDR features
            "call_duration_avg",
            "calls_per_hour",
            "unique_numbers_called",
            "roaming_minutes",
            "premium_rate_calls",
            "short_code_calls",

            # Billing features
            "monthly_charge",
            "charge_trend_3m",
            "payment_history_score",
            "overdue_balance",

            # Pattern features
            "odd_hour_activity",
            "geographic_impossibility",
            "device_change_frequency",

            # Network features
            "tower_switches_per_hour",
            "sim_swap_count",
            "network_anomaly_score",
        ]

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create fraud detection features"""
        features = pd.DataFrame()

        # CDR patterns
        features["call_duration_avg"] = df.get("call_duration_avg", 60)
        features["call_duration_std"] = df.get("call_duration_std", 30)
        features["calls_per_hour"] = df.get("calls_per_hour", 5)
        features["unique_numbers_called"] = df.get("unique_numbers_called", 20)
        features["roaming_minutes"] = df.get("roaming_minutes", 0)
        features["international_calls"] = df.get("international_calls", 0)
        features["short_code_calls"] = df.get("short_code_calls", 0)
        features["premium_rate_calls"] = df.get("premium_rate_calls", 0)

        # Billing patterns
        features["monthly_charge"] = df.get("monthly_charge", 100)
        features["charge_trend_3m"] = df.get("charge_trend_3m", 0)
        features["payment_history_score"] = df.get("payment_score", 0.8)
        features["overdue_balance"] = df.get("overdue_balance", 0)

        # Behavioral patterns
        features["burst_call_pattern"] = df.get("burst_pattern_score", 0)
        features["odd_hour_activity"] = df.get("odd_hour_call_ratio", 0.1)
        features["geographic_impossibility"] = df.get("geo_impossibility_score", 0)
        features["device_change_frequency"] = df.get("device_change_count", 0)

        # Network patterns
        features["tower_switches_per_hour"] = df.get("tower_switches_per_hour", 1)
        features["sim_swap_count"] = df.get("sim_swap_count", 0)
        features["network_anomaly_score"] = df.get("network_anomaly_score", 0)

        return features[self.feature_names]


class FraudDetector:
    """
    Multi-layer fraud detection system.

    Layers:
    1. Rule-based detection (deterministic patterns)
    2. ML-based anomaly detection (Isolation Forest)
    3. Ensemble scoring (combines both)
    """

    def __init__(
        self,
        model_dir: str = "ml/fraud_detection",
        detection_threshold: float = 0.7,
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.detection_threshold = detection_threshold

        self.feature_engineer = FeatureEngineer()
        self.isolation_forest = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self._fit_features = None

        # Fraud detection rules
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> List[Dict]:
        """Initialize fraud detection rules"""
        return [
            {
                "name": "sim_box_detection",
                "type": FraudType.SIM_BOX,
                "conditions": [
                    {"feature": "calls_per_hour", "op": ">", "threshold": 50},
                    {"feature": "unique_numbers_called", "op": "<", "threshold": 5},
                    {"feature": "call_duration_avg", "op": "<", "threshold": 30},
                ],
                "weight": 0.4,
                "description": "High call volume to few numbers with short duration",
            },
            {
                "name": "roaming_fraud_detection",
                "type": FraudType.ROAMING_FRAUD,
                "conditions": [
                    {"feature": "roaming_minutes", "op": ">", "threshold": 500},
                    {"feature": "monthly_charge", "op": ">", "threshold": 500},
                    {"feature": "charge_trend_3m", "op": ">", "threshold": 0.5},
                ],
                "weight": 0.3,
                "description": "Sudden spike in roaming usage and charges",
            },
            {
                "name": "revenue_leakage_detection",
                "type": FraudType.REVENUE_LEAKAGE,
                "conditions": [
                    {"feature": "premium_rate_calls", "op": ">", "threshold": 10},
                    {"feature": "short_code_calls", "op": ">", "threshold": 20},
                    {"feature": "payment_history_score", "op": "<", "threshold": 0.5},
                ],
                "weight": 0.3,
                "description": "Excessive premium rate and short code usage",
            },
            {
                "name": "subscription_fraud_detection",
                "type": FraudType.SUBSCRIPTION_FRAUD,
                "conditions": [
                    {"feature": "device_change_frequency", "op": ">", "threshold": 5},
                    {"feature": "sim_swap_count", "op": ">", "threshold": 3},
                    {"feature": "overdue_balance", "op": ">", "threshold": 200},
                ],
                "weight": 0.25,
                "description": "Frequent device/SIM changes with payment issues",
            },
            {
                "name": "irs_fraud_detection",
                "type": FraudType.INTERNATIONAL_REVENUE_SHARE_FRAUD,
                "conditions": [
                    {"feature": "premium_rate_calls", "op": ">", "threshold": 5},
                    {"feature": "call_duration_avg", "op": ">", "threshold": 300},
                    {"feature": "odd_hour_activity", "op": ">", "threshold": 0.3},
                ],
                "weight": 0.3,
                "description": "Long premium rate calls during odd hours",
            },
            {
                "name": "call_forwarding_fraud_detection",
                "type": FraudType.CALL_FORWARDING_FRAUD,
                "conditions": [
                    {"feature": "tower_switches_per_hour", "op": ">", "threshold": 20},
                    {"feature": "geographic_impossibility", "op": ">", "threshold": 0.5},
                    {"feature": "roaming_minutes", "op": ">", "threshold": 100},
                ],
                "weight": 0.35,
                "description": "Rapid tower switching with geographic impossibility",
            },
        ]

    def train(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
    ) -> Dict:
        """
        Train fraud detection model.

        Args:
            X: Feature matrix
            y: Optional fraud labels for supervised learning

        Returns:
            Training metrics
        """
        if not SKLEARN_AVAILABLE:
            return {"status": "sklearn_not_available", "method": "rule_based_only"}

        # Store feature names for validation
        self._fit_features = list(X.columns)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train Isolation Forest
        contamination = y.mean() if y is not None else 0.05
        self.isolation_forest = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        self.isolation_forest.fit(X_scaled)

        return {
            "status": "trained",
            "n_estimators": 100,
            "contamination": contamination,
            "method": "isolation_forest",
        }

    def detect(
        self,
        df: pd.DataFrame,
        customer_ids: Optional[List[str]] = None,
        transaction_ids: Optional[List[str]] = None,
    ) -> List[FraudDetection]:
        """
        Detect fraud in customer data.

        Args:
            df: Customer data with features
            customer_ids: Optional customer IDs
            transaction_ids: Optional transaction IDs

        Returns:
            List of FraudDetection results
        """
        if customer_ids is None:
            customer_ids = [f"CUST_{i:06d}" for i in range(len(df))]

        if transaction_ids is None:
            transaction_ids = [f"TXN_{i:08d}" for i in range(len(df))]

        # Get engineered features
        X = self.feature_engineer.engineer_features(df)

        # Rule-based detection
        rule_scores = self._rule_based_detection(X)

        # ML-based detection
        ml_scores = self._ml_based_detection(X) if self.isolation_forest else None

        # Combine scores
        detections = []
        for i in range(len(df)):
            fraud_score = 0
            fraud_types = []
            rules_triggered = []
            features_contributing = []

            # Rule-based scores
            for score, rule in rule_scores[i]:
                if score > 0:
                    fraud_score += score * rule["weight"]
                    fraud_types.append(rule["type"])
                    rules_triggered.append(rule["name"])

            # ML-based scores
            if ml_scores is not None:
                ml_score = ml_scores[i]
                fraud_score = max(fraud_score, ml_score * 0.5)

            # Normalize score
            fraud_score = min(1.0, fraud_score)

            if fraud_score >= self.detection_threshold:
                # Determine primary fraud type
                primary_type = self._determine_primary_fraud_type(fraud_types)

                # Determine severity
                severity = self._determine_severity(fraud_score)

                # Get contributing features
                features_contributing = self._get_contributing_features(
                    X.iloc[i], rule_scores[i]
                )

                # Generate recommendation
                recommendation = self._generate_recommendation(
                    primary_type, fraud_score
                )

                detections.append(FraudDetection(
                    transaction_id=transaction_ids[i],
                    customer_id=customer_ids[i],
                    fraud_type=primary_type,
                    fraud_score=float(fraud_score),
                    severity=severity,
                    confidence=float(fraud_score),
                    rules_triggered=rules_triggered,
                    features_contributing=features_contributing,
                    recommendation=recommendation,
                    timestamp=pd.Timestamp.now().isoformat(),
                ))

        return detections

    def _rule_based_detection(
        self,
        X: pd.DataFrame,
    ) -> List[List[Tuple[float, Dict]]]:
        """Apply rule-based fraud detection"""
        all_scores = []

        for idx, row in X.iterrows():
            row_scores = []
            for rule in self.rules:
                score = 0
                conditions_met = 0
                total_conditions = len(rule["conditions"])

                for condition in rule["conditions"]:
                    feature = condition["feature"]
                    if feature in row.index:
                        value = row[feature]
                        op = condition["op"]
                        threshold = condition["threshold"]

                        if op == ">" and value > threshold:
                            conditions_met += 1
                        elif op == "<" and value < threshold:
                            conditions_met += 1

                if conditions_met == total_conditions:
                    score = 1.0
                elif conditions_met > 0:
                    score = conditions_met / total_conditions * 0.7

                row_scores.append((score, rule))

            all_scores.append(row_scores)

        return all_scores

    def _ml_based_detection(
        self,
        X: pd.DataFrame,
    ) -> np.ndarray:
        """Apply ML-based anomaly detection"""
        if not SKLEARN_AVAILABLE or self.isolation_forest is None:
            return np.zeros(len(X))

        # Ensure features match training features exactly
        if self._fit_features is not None:
            X_aligned = X[self._fit_features].copy()
        else:
            X_aligned = X

        X_scaled = self.scaler.transform(X_aligned)
        predictions = self.isolation_forest.predict(X_scaled)
        scores = -self.isolation_forest.score_samples(X_scaled)

        # Normalize scores to [0, 1]
        if scores.max() > scores.min():
            scores = (scores - scores.min()) / (scores.max() - scores.min())

        return scores

    def _determine_primary_fraud_type(
        self,
        fraud_types: List[FraudType],
    ) -> FraudType:
        """Determine primary fraud type from multiple detections"""
        if not fraud_types:
            return FraudType.CDR_FABRICATION

        # Return most common type
        from collections import Counter
        most_common = Counter(fraud_types).most_common(1)
        return most_common[0][0] if most_common else FraudType.CDR_FABRICATION

    def _determine_severity(self, fraud_score: float) -> FraudSeverity:
        """Determine fraud severity based on score"""
        if fraud_score >= 0.9:
            return FraudSeverity.CRITICAL
        elif fraud_score >= 0.75:
            return FraudSeverity.HIGH
        elif fraud_score >= 0.5:
            return FraudSeverity.MEDIUM
        else:
            return FraudSeverity.LOW

    def _get_contributing_features(
        self,
        feature_vector: pd.Series,
        rule_scores: List[Tuple[float, Dict]],
    ) -> List[Tuple[str, float]]:
        """Get top contributing features"""
        features = []
        for score, rule in rule_scores:
            if score > 0:
                for condition in rule["conditions"]:
                    feature = condition["feature"]
                    if feature in feature_vector.index:
                        features.append((feature, score))
        return features[:5]

    def _generate_recommendation(
        self,
        fraud_type: FraudType,
        fraud_score: float,
    ) -> str:
        """Generate recommendation based on fraud type and score"""
        recommendations = {
            FraudType.SIM_BOX: "Block SIM and investigate device. Report to fraud team.",
            FraudType.ROAMING_FRAUD: "Restrict roaming and verify customer identity.",
            FraudType.REVENUE_LEAKAGE: "Review premium rate subscriptions and block suspicious numbers.",
            FraudType.SUBSCRIPTION_FRAUD: "Suspend account and require identity verification.",
            FraudType.INTERNATIONAL_REVENUE_SHARE_FRAUD: "Block premium rate access and investigate.",
            FraudType.CALL_FORWARDING_FRAUD: "Monitor call patterns and implement geofencing.",
            FraudType.CDR_FABRICATION: "Investigate CDR system and audit billing records.",
        }
        return recommendations.get(fraud_type, "Review and investigate fraud pattern.")

    def get_fraud_summary(self, detections: List[FraudDetection]) -> Dict:
        """Get summary of fraud detections"""
        summary = {
            "total_detections": len(detections),
            "by_severity": {},
            "by_type": {},
            "avg_fraud_score": 0,
            "high_risk_customers": [],
        }

        if not detections:
            return summary

        severity_counts = {}
        type_counts = {}
        total_score = 0

        for det in detections:
            severity_counts[det.severity.value] = severity_counts.get(det.severity.value, 0) + 1
            type_counts[det.fraud_type.value] = type_counts.get(det.fraud_type.value, 0) + 1
            total_score += det.fraud_score

            if det.severity in [FraudSeverity.HIGH, FraudSeverity.CRITICAL]:
                summary["high_risk_customers"].append({
                    "customer_id": det.customer_id,
                    "fraud_type": det.fraud_type.value,
                    "fraud_score": det.fraud_score,
                })

        summary["by_severity"] = severity_counts
        summary["by_type"] = type_counts
        summary["avg_fraud_score"] = total_score / len(detections)

        return summary


def generate_fraud_data(
    n_samples: int = 10000,
    fraud_rate: float = 0.05,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Generate synthetic data with fraud patterns"""
    rng = np.random.default_rng(random_state)

    n_fraud = int(n_samples * fraud_rate)
    n_normal = n_samples - n_fraud

    # Normal customers
    normal_data = {
        "calls_per_hour": rng.poisson(5, n_normal),
        "unique_numbers_called": rng.poisson(20, n_normal),
        "call_duration_avg": rng.exponential(120, n_normal),
        "roaming_minutes": rng.exponential(10, n_normal),
        "monthly_charge": rng.lognormal(4.5, 0.5, n_normal),
        "charge_trend_3m": rng.normal(0, 0.1, n_normal),
        "payment_history_score": rng.normal(0.8, 0.1, n_normal).clip(0, 1),
        "overdue_balance": rng.exponential(20, n_normal),
        "premium_rate_calls": rng.poisson(0.5, n_normal),
        "short_code_calls": rng.poisson(1, n_normal),
        "device_change_frequency": rng.poisson(0.2, n_normal),
        "sim_swap_count": rng.poisson(0.1, n_normal),
        "tower_switches_per_hour": rng.poisson(1, n_normal),
        "odd_hour_activity": rng.normal(0.1, 0.05, n_normal).clip(0, 1),
        "geographic_impossibility": rng.normal(0, 0.05, n_normal).clip(0, 1),
        "network_anomaly_score": rng.normal(0, 0.1, n_normal).clip(0, 1),
    }

    normal_df = pd.DataFrame(normal_data)
    normal_labels = pd.Series([0] * n_normal)

    # Fraudulent customers (various types)
    fraud_labels = []
    fraud_dfs = []

    # SIM box fraud
    n_sim_box = n_fraud // 4
    sim_box_data = {
        "calls_per_hour": rng.poisson(60, n_sim_box),
        "unique_numbers_called": rng.poisson(3, n_sim_box),
        "call_duration_avg": rng.exponential(20, n_sim_box),
        "roaming_minutes": rng.exponential(5, n_sim_box),
        "monthly_charge": rng.lognormal(5, 0.3, n_sim_box),
        "charge_trend_3m": rng.normal(0.3, 0.1, n_sim_box),
        "payment_history_score": rng.normal(0.7, 0.1, n_sim_box),
        "overdue_balance": rng.exponential(30, n_sim_box),
        "premium_rate_calls": rng.poisson(1, n_sim_box),
        "short_code_calls": rng.poisson(2, n_sim_box),
        "device_change_frequency": rng.poisson(0.5, n_sim_box),
        "sim_swap_count": rng.poisson(0.2, n_sim_box),
        "tower_switches_per_hour": rng.poisson(2, n_sim_box),
        "odd_hour_activity": rng.normal(0.15, 0.05, n_sim_box).clip(0, 1),
        "geographic_impossibility": rng.normal(0.05, 0.02, n_sim_box).clip(0, 1),
        "network_anomaly_score": rng.normal(0.15, 0.05, n_sim_box).clip(0, 1),
    }
    fraud_dfs.append(pd.DataFrame(sim_box_data))
    fraud_labels.extend([1] * n_sim_box)

    # Roaming fraud
    n_roaming = n_fraud // 4
    roaming_data = {
        "calls_per_hour": rng.poisson(8, n_roaming),
        "unique_numbers_called": rng.poisson(15, n_roaming),
        "call_duration_avg": rng.exponential(100, n_roaming),
        "roaming_minutes": rng.exponential(600, n_roaming),
        "monthly_charge": rng.lognormal(5.5, 0.5, n_roaming),
        "charge_trend_3m": rng.normal(0.6, 0.1, n_roaming),
        "payment_history_score": rng.normal(0.6, 0.15, n_roaming),
        "overdue_balance": rng.exponential(100, n_roaming),
        "premium_rate_calls": rng.poisson(2, n_roaming),
        "short_code_calls": rng.poisson(3, n_roaming),
        "device_change_frequency": rng.poisson(1, n_roaming),
        "sim_swap_count": rng.poisson(2, n_roaming),
        "tower_switches_per_hour": rng.poisson(3, n_roaming),
        "odd_hour_activity": rng.normal(0.2, 0.1, n_roaming).clip(0, 1),
        "geographic_impossibility": rng.normal(0.1, 0.05, n_roaming).clip(0, 1),
        "network_anomaly_score": rng.normal(0.2, 0.1, n_roaming).clip(0, 1),
    }
    fraud_dfs.append(pd.DataFrame(roaming_data))
    fraud_labels.extend([1] * n_roaming)

    # Revenue leakage fraud
    n_revenue = n_fraud // 3
    revenue_data = {
        "calls_per_hour": rng.poisson(10, n_revenue),
        "unique_numbers_called": rng.poisson(25, n_revenue),
        "call_duration_avg": rng.exponential(150, n_revenue),
        "roaming_minutes": rng.exponential(20, n_revenue),
        "monthly_charge": rng.lognormal(5, 0.4, n_revenue),
        "charge_trend_3m": rng.normal(0.2, 0.1, n_revenue),
        "payment_history_score": rng.normal(0.4, 0.15, n_revenue),
        "overdue_balance": rng.exponential(80, n_revenue),
        "premium_rate_calls": rng.poisson(15, n_revenue),
        "short_code_calls": rng.poisson(30, n_revenue),
        "device_change_frequency": rng.poisson(1, n_revenue),
        "sim_swap_count": rng.poisson(1, n_revenue),
        "tower_switches_per_hour": rng.poisson(2, n_revenue),
        "odd_hour_activity": rng.normal(0.25, 0.1, n_revenue).clip(0, 1),
        "geographic_impossibility": rng.normal(0.08, 0.03, n_revenue).clip(0, 1),
        "network_anomaly_score": rng.normal(0.18, 0.08, n_revenue).clip(0, 1),
    }
    fraud_dfs.append(pd.DataFrame(revenue_data))
    fraud_labels.extend([1] * n_revenue)

    # Other fraud
    n_other = n_fraud - n_sim_box - n_roaming - n_revenue
    other_data = {
        "calls_per_hour": rng.poisson(15, n_other),
        "unique_numbers_called": rng.poisson(10, n_other),
        "call_duration_avg": rng.exponential(80, n_other),
        "roaming_minutes": rng.exponential(100, n_other),
        "monthly_charge": rng.lognormal(5, 0.5, n_other),
        "charge_trend_3m": rng.normal(0.4, 0.15, n_other),
        "payment_history_score": rng.normal(0.5, 0.2, n_other),
        "overdue_balance": rng.exponential(60, n_other),
        "premium_rate_calls": rng.poisson(8, n_other),
        "short_code_calls": rng.poisson(15, n_other),
        "device_change_frequency": rng.poisson(3, n_other),
        "sim_swap_count": rng.poisson(2, n_other),
        "tower_switches_per_hour": rng.poisson(5, n_other),
        "odd_hour_activity": rng.normal(0.3, 0.1, n_other).clip(0, 1),
        "geographic_impossibility": rng.normal(0.15, 0.05, n_other).clip(0, 1),
        "network_anomaly_score": rng.normal(0.25, 0.1, n_other).clip(0, 1),
    }
    fraud_dfs.append(pd.DataFrame(other_data))
    fraud_labels.extend([1] * n_other)

    # Combine
    fraud_df = pd.concat(fraud_dfs, ignore_index=True)
    fraud_labels = pd.Series(fraud_labels)

    # Combine normal and fraud
    combined_df = pd.concat([normal_df, fraud_df], ignore_index=True)
    combined_labels = pd.concat([normal_labels, fraud_labels], ignore_index=True)

    # Shuffle
    shuffle_idx = rng.permutation(len(combined_df))
    combined_df = combined_df.iloc[shuffle_idx]
    combined_labels = combined_labels.iloc[shuffle_idx]

    return combined_df, combined_labels


if __name__ == "__main__":
    # Example usage
    print("Training Fraud Detection Model...")

    # Generate data
    X, y = generate_fraud_data(n_samples=10000, fraud_rate=0.05)
    print(f"Generated {len(X)} samples, fraud rate: {y.mean():.2%}")

    # Initialize detector
    detector = FraudDetector()

    # Train model
    results = detector.train(X, y)
    print(f"Training results: {results}")

    # Detect fraud
    detections = detector.detect(X.head(100))
    print(f"\nDetected {len(detections)} fraud cases")

    # Get summary
    summary = detector.get_fraud_summary(detections)
    print(f"\nFraud Summary:")
    print(f"  Total detections: {summary['total_detections']}")
    print(f"  By severity: {summary['by_severity']}")
    print(f"  By type: {summary['by_type']}")
    print(f"  Avg fraud score: {summary['avg_fraud_score']:.4f}")
