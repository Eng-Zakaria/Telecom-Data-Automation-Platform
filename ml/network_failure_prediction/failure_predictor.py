"""
Network Failure Prediction Model

Predicts network failures and degradation using:
- Time series analysis of KPIs
- Anomaly detection on network metrics
- Predictive maintenance scheduling
- Root cause analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from datetime import datetime, timedelta

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Using fallback implementation.")


class FailureType(Enum):
    """Network failure types"""
    HARDWARE_FAILURE = "hardware_failure"
    SOFTWARE_GLITCH = "software_glitch"
    OVERLOAD = "overload"
    INTERFERENCE = "interference"
    POWER_ISSUE = "power_issue"
    BACKHAUL_FAILURE = "backhaul_failure"
    FIBER_CUT = "fiber_cut"


class PredictionHorizon(Enum):
    """Prediction horizons"""
    HORSE_1H = "1_hour"
    HORSE_6H = "6_hours"
    HORSE_24H = "24_hours"
    HORSE_7D = "7_days"


@dataclass
class FailurePrediction:
    """Network failure prediction result"""
    tower_id: str
    prediction_horizon: PredictionHorizon
    failure_probability: float
    predicted_failure_type: FailureType
    confidence: float
    contributing_factors: List[Tuple[str, float]]
    recommended_action: str
    timestamp: str


class NetworkFailurePredictor:
    """
    Network failure prediction model.

    Predicts:
    - Tower failures (1h, 6h, 24h, 7d horizons)
    - Degradation patterns
    - Maintenance priorities
    - Root cause analysis
    """

    def __init__(
        self,
        model_dir: str = "ml/network_failure_prediction",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.models = {}
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None

        # Feature engineering
        self.feature_names = [
            "signal_strength_dbm",
            "dropped_call_rate",
            "congestion_level",
            "latency_ms",
            "throughput_mbps",
            "error_rate",
            "temperature_celsius",
            "power_consumption_kw",
            "utilization_percent",
            "historical_failure_count_7d",
            "maintenance_days_since",
            "age_months",
        ]

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        horizon: PredictionHorizon = PredictionHorizon.HORSE_24H,
    ) -> Dict:
        """
        Train failure prediction model for specified horizon.

        Args:
            X: Feature matrix
            y: Binary failure labels
            horizon: Prediction horizon

        Returns:
            Training metrics
        """
        if not SKLEARN_AVAILABLE:
            return {"status": "sklearn_not_available", "method": "fallback"}

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train Gradient Boosting classifier
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            random_state=42,
        )
        model.fit(X_scaled, y)

        # Evaluate
        from sklearn.metrics import roc_auc_score
        y_pred = model.predict(X_scaled)
        y_prob = model.predict_proba(X_scaled)[:, 1]

        metrics = {
            "horizon": horizon.value,
            "roc_auc": roc_auc_score(y, y_prob),
            "accuracy": (y_pred == y).mean(),
            "method": "gradient_boosting",
        }

        self.models[horizon.value] = model
        return metrics

    def predict(
        self,
        X: pd.DataFrame,
        tower_ids: Optional[List[str]] = None,
        horizon: PredictionHorizon = PredictionHorizon.HORSE_24H,
    ) -> List[FailurePrediction]:
        """
        Predict network failures.

        Args:
            X: Feature matrix
            tower_ids: Optional tower IDs
            horizon: Prediction horizon

        Returns:
            List of FailurePrediction objects
        """
        if tower_ids is None:
            tower_ids = [f"TOWER_{i:06d}" for i in range(len(X))]

        predictions = []

        for idx, row in X.iterrows():
            # Calculate failure probability
            if SKLEARN_AVAILABLE and self.models.get(horizon.value) is not None:
                X_scaled = self.scaler.transform(X.iloc[idx:idx+1])
                prob = self.models[horizon.value].predict_proba(X_scaled)[0, 1]
                feature_importance = dict(zip(
                    self.feature_names,
                    self.models[horizon.value].feature_importances_.tolist()
                ))
            else:
                # Fallback: calculate based on feature thresholds
                prob = self._calculate_fallback_probability(row)
                feature_importance = self._get_fallback_importance(row)

            # Determine failure type
            failure_type = self._predict_failure_type(row, prob)

            # Get contributing factors
            contributing_factors = self._get_contributing_factors(row, feature_importance)

            # Generate recommended action
            recommended_action = self._generate_recommended_action(
                failure_type, prob, row
            )

            predictions.append(FailurePrediction(
                tower_id=tower_ids[idx],
                prediction_horizon=horizon,
                failure_probability=float(prob),
                predicted_failure_type=failure_type,
                confidence=float(prob),
                contributing_factors=contributing_factors,
                recommended_action=recommended_action,
                timestamp=datetime.now().isoformat(),
            ))

        return predictions

    def _calculate_fallback_probability(self, row: pd.Series) -> float:
        """Calculate fallback failure probability"""
        # Simple heuristic based on feature thresholds
        prob = 0.1  # Base probability

        # Increase probability for degraded metrics
        if row.get("dropped_call_rate", 0) > 0.05:
            prob += 0.2
        if row.get("congestion_level", 0) > 0.8:
            prob += 0.15
        if row.get("signal_strength_dbm", -90) < -100:
            prob += 0.1
        if row.get("error_rate", 0) > 0.01:
            prob += 0.15
        if row.get("temperature_celsius", 25) > 45:
            prob += 0.1
        if row.get("historical_failure_count_7d", 0) > 3:
            prob += 0.2

        return min(1.0, prob)

    def _get_fallback_importance(self, row: pd.Series) -> Dict[str, float]:
        """Get fallback feature importance"""
        return {
            "dropped_call_rate": 0.25,
            "congestion_level": 0.2,
            "error_rate": 0.2,
            "historical_failure_count_7d": 0.15,
            "signal_strength_dbm": 0.1,
            "temperature_celsius": 0.1,
        }

    def _predict_failure_type(
        self,
        row: pd.Series,
        prob: float,
    ) -> FailureType:
        """Predict failure type based on features"""
        if prob < 0.3:
            return FailureType.SOFTWARE_GLITCH

        # Determine most likely failure type
        if row.get("temperature_celsius", 25) > 50:
            return FailureType.HARDWARE_FAILURE
        elif row.get("power_consumption_kw", 0) > 5:
            return FailureType.POWER_ISSUE
        elif row.get("congestion_level", 0) > 0.9:
            return FailureType.OVERLOAD
        elif row.get("error_rate", 0) > 0.05:
            return FailureType.INTERFERENCE
        elif row.get("latency_ms", 0) > 100:
            return FailureType.BACKHAUL_FAILURE
        else:
            return FailureType.HARDWARE_FAILURE

    def _get_contributing_factors(
        self,
        row: pd.Series,
        feature_importance: Dict[str, float],
    ) -> List[Tuple[str, float]]:
        """Get top contributing factors"""
        factors = []
        for feature, importance in sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]:
            if feature in row.index:
                value = row[feature]
                factors.append((feature, float(value)))
        return factors

    def _generate_recommended_action(
        self,
        failure_type: FailureType,
        prob: float,
        row: pd.Series,
    ) -> str:
        """Generate recommended action based on failure type and probability"""
        actions = {
            FailureType.HARDWARE_FAILURE: "Schedule immediate hardware inspection and replacement",
            FailureType.SOFTWARE_GLITCH: "Apply software patch and restart services",
            FailureType.OVERLOAD: "Implement traffic redistribution or add capacity",
            FailureType.INTERFERENCE: "Investigate interference sources and adjust antenna parameters",
            FailureType.POWER_ISSUE: "Check power supply and backup systems",
            FailureType.BACKHAUL_FAILURE: "Inspect backhaul links and switch to redundant path",
            FailureType.FIBER_CUT: "Locate and repair fiber cut, activate backup route",
        }

        base_action = actions.get(failure_type, "Investigate and monitor")

        if prob > 0.8:
            return f"URGENT: {base_action}. Deploy field team immediately."
        elif prob > 0.5:
            return f"HIGH PRIORITY: {base_action}. Schedule within 24 hours."
        else:
            return f"{base_action}. Monitor closely."

    def get_maintenance_schedule(
        self,
        predictions: List[FailurePrediction],
    ) -> Dict:
        """Generate maintenance schedule from predictions"""
        schedule = {
            "immediate_action": [],
            "within_24h": [],
            "within_7d": [],
            "monitor": [],
        }

        for pred in predictions:
            if pred.failure_probability >= 0.8:
                schedule["immediate_action"].append({
                    "tower_id": pred.tower_id,
                    "failure_type": pred.predicted_failure_type.value,
                    "probability": pred.failure_probability,
                })
            elif pred.failure_probability >= 0.5:
                schedule["within_24h"].append({
                    "tower_id": pred.tower_id,
                    "failure_type": pred.predicted_failure_type.value,
                    "probability": pred.failure_probability,
                })
            elif pred.failure_probability >= 0.3:
                schedule["within_7d"].append({
                    "tower_id": pred.tower_id,
                    "failure_type": pred.predicted_failure_type.value,
                    "probability": pred.failure_probability,
                })
            else:
                schedule["monitor"].append({
                    "tower_id": pred.tower_id,
                    "failure_type": pred.predicted_failure_type.value,
                    "probability": pred.failure_probability,
                })

        return schedule


def generate_network_kpi_data(
    n_towers: int = 1000,
    n_days: int = 30,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Generate synthetic network KPI data"""
    rng = np.random.default_rng(random_state)

    # Generate tower data
    towers = []
    labels = []

    for i in range(n_towers):
        # Base characteristics
        base_signal = rng.normal(-85, 10)
        base_dropped = rng.exponential(0.02)
        base_congestion = rng.beta(2, 5)
        base_latency = rng.exponential(50)
        base_temperature = rng.normal(25, 5)

        # Some towers are degraded
        is_degraded = rng.random() < 0.1
        is_failing = rng.random() < 0.05

        if is_degraded:
            base_signal -= 10
            base_dropped *= 3
            base_congestion *= 2
            base_latency *= 2
            base_temperature += 15

        if is_failing:
            base_signal -= 20
            base_dropped *= 5
            base_congestion = min(1.0, base_congestion + 0.3)
            base_latency *= 3
            base_temperature += 25

        tower_data = {
            "tower_id": f"TOWER_{i:06d}",
            "signal_strength_dbm": base_signal + rng.normal(0, 2),
            "dropped_call_rate": min(0.5, base_dropped + rng.exponential(0.01)),
            "congestion_level": min(1.0, base_congestion + rng.normal(0, 0.1)),
            "latency_ms": max(10, base_latency + rng.exponential(10)),
            "throughput_mbps": max(1, 50 - base_congestion * 30 + rng.normal(0, 5)),
            "error_rate": min(0.1, base_dropped * 0.5 + rng.exponential(0.005)),
            "temperature_celsius": base_temperature + rng.normal(0, 3),
            "power_consumption_kw": max(1, 3 + base_temperature * 0.05 + rng.normal(0, 0.5)),
            "utilization_percent": min(100, base_congestion * 80 + rng.normal(0, 10)),
            "historical_failure_count_7d": int(rng.poisson(2 if is_failing else 0.5)),
            "maintenance_days_since": int(rng.exponential(90)),
            "age_months": int(rng.exponential(36)),
        }

        towers.append(tower_data)
        labels.append(1 if is_failing else 0)

    return pd.DataFrame(towers), pd.Series(labels)


if __name__ == "__main__":
    # Example usage
    print("Training Network Failure Prediction Model...")

    # Generate data
    X, y = generate_network_kpi_data(n_towers=1000)
    print(f"Generated {len(X)} tower records, failure rate: {y.mean():.2%}")

    # Initialize predictor
    predictor = NetworkFailurePredictor()

    # Train model
    results = predictor.train(X, y)
    print(f"Training results: {results}")

    # Make predictions
    predictions = predictor.predict(X.head(50))
    print(f"\nPredictions for 50 towers:")

    for pred in predictions[:5]:
        print(f"  {pred.tower_id}: {pred.failure_probability:.1%} "
              f"({pred.predicted_failure_type.value})")
        print(f"    Action: {pred.recommended_action}")

    # Get maintenance schedule
    schedule = predictor.get_maintenance_schedule(predictions)
    print(f"\nMaintenance Schedule:")
    print(f"  Immediate action: {len(schedule['immediate_action'])} towers")
    print(f"  Within 24h: {len(schedule['within_24h'])} towers")
    print(f"  Within 7d: {len(schedule['within_7d'])} towers")
    print(f"  Monitor: {len(schedule['monitor'])} towers")
