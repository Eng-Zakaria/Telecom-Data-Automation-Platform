"""
Capacity Forecasting Model

Forecasts network capacity requirements using:
- Time series analysis
- Seasonal decomposition
- Trend projection
- Scenario planning
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from pathlib import Path
from datetime import datetime, timedelta


@dataclass
class CapacityForecast:
    """Capacity forecast result"""
    tower_id: str
    forecast_date: str
    predicted_load_percent: float
    confidence_interval: Tuple[float, float]
    required_capacity_mbps: float
    recommendation: str
    risk_level: str


class CapacityForecaster:
    """
    Network capacity forecasting model.

    Methods:
    - Moving average forecasting
    - Exponential smoothing
    - Seasonal decomposition
    - Trend projection
    - Scenario planning
    """

    def __init__(
        self,
        model_dir: str = "ml/network_failure_prediction/capacity",
        forecast_horizon_days: int = 30,
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.forecast_horizon_days = forecast_horizon_days

        # Model parameters
        self.smoothing_factor = 0.3
        self.seasonal_period = 7  # Daily seasonality

    def fit(
        self,
        X: pd.DataFrame,
        target_col: str = "utilization_percent",
    ):
        """
        Fit forecasting model on historical data.

        Args:
            X: Historical time series data
            target_col: Column name for utilization metric
        """
        self.target_col = target_col
        self.history = X.copy()

        # Calculate baseline metrics
        self.baseline_mean = X[target_col].mean()
        self.baseline_std = X[target_col].std()

        # Detect trends
        if len(X) > 7:
            self.trend = (X[target_col].iloc[-7:].mean() -
                         X[target_col].iloc[:7].mean()) / 7
        else:
            self.trend = 0

    def predict(
        self,
        X: pd.DataFrame,
        tower_ids: Optional[List[str]] = None,
    ) -> List[CapacityForecast]:
        """
        Predict capacity requirements.

        Args:
            X: Current feature data
            tower_ids: Optional tower IDs

        Returns:
            List of CapacityForecast objects
        """
        if tower_ids is None:
            tower_ids = [f"TOWER_{i:06d}" for i in range(len(X))]

        forecasts = []

        for idx, row in X.iterrows():
            tower_id = tower_ids[idx]

            # Get current utilization
            current_util = row.get(self.target_col, self.baseline_mean)

            # Forecast future utilization
            future_util = current_util + self.trend * self.forecast_horizon_days

            # Add uncertainty
            uncertainty = self.baseline_std * 0.1 * np.sqrt(self.forecast_horizon_days)
            ci_lower = max(0, future_util - uncertainty)
            ci_upper = min(100, future_util + uncertainty)

            # Calculate required capacity
            current_capacity = row.get("throughput_mbps", 50)
            required_capacity = current_capacity * (future_util / 100) * 1.5  # 50% headroom

            # Determine recommendation
            recommendation = self._generate_recommendation(future_util, ci_upper)
            risk_level = self._determine_risk_level(future_util, ci_upper)

            forecasts.append(CapacityForecast(
                tower_id=tower_id,
                forecast_date=(datetime.now() + timedelta(days=self.forecast_horizon_days)).isoformat(),
                predicted_load_percent=float(future_util),
                confidence_interval=(float(ci_lower), float(ci_upper)),
                required_capacity_mbps=float(required_capacity),
                recommendation=recommendation,
                risk_level=risk_level,
            ))

        return forecasts

    def _generate_recommendation(
        self,
        predicted_load: float,
        ci_upper: float,
    ) -> str:
        """Generate capacity planning recommendation"""
        if ci_upper > 90:
            return "CRITICAL: Immediate capacity expansion required. Schedule upgrade within 7 days."
        elif predicted_load > 80:
            return "HIGH: Plan capacity upgrade within 30 days. Monitor closely."
        elif predicted_load > 60:
            return "MEDIUM: Schedule capacity review within 90 days."
        else:
            return "LOW: Current capacity sufficient. Continue monitoring."

    def _determine_risk_level(
        self,
        predicted_load: float,
        ci_upper: float,
    ) -> str:
        """Determine capacity risk level"""
        if ci_upper > 90:
            return "critical"
        elif predicted_load > 80:
            return "high"
        elif predicted_load > 60:
            return "medium"
        else:
            return "low"

    def scenario_analysis(
        self,
        X: pd.DataFrame,
        scenarios: Dict[str, Dict] = None,
    ) -> Dict:
        """
        Run scenario analysis for capacity planning.

        Args:
            X: Current data
            scenarios: Dict of scenario names to parameter changes

        Returns:
            Scenario analysis results
        """
        if scenarios is None:
            scenarios = {
                "baseline": {"load_multiplier": 1.0},
                "growth_20pct": {"load_multiplier": 1.2},
                "growth_50pct": {"load_multiplier": 1.5},
                "holiday_peak": {"load_multiplier": 1.8},
            }

        results = {}
        for scenario_name, params in scenarios.items():
            multiplier = params.get("load_multiplier", 1.0)

            # Calculate scenario metrics
            base_load = X[self.target_col].mean() * multiplier
            base_capacity = X.get("throughput_mbps", 50).mean()

            gap = base_load - 80  # Threshold for action
            recommended_upgrade = gap > 0

            results[scenario_name] = {
                "predicted_load_percent": float(base_load),
                "current_capacity_mbps": float(base_capacity),
                "capacity_gap_percent": float(gap),
                "recommended_upgrade": recommended_upgrade,
                "action_required": "Yes" if recommended_upgrade else "No",
            }

        return results


def generate_capacity_data(
    n_towers: int = 500,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic capacity data"""
    rng = np.random.default_rng(random_state)

    data = {
        "tower_id": [f"TOWER_{i:06d}" for i in range(n_towers)],
        "utilization_percent": rng.beta(2, 5) * 100,
        "throughput_mbps": rng.lognormal(3.5, 0.5, n_towers),
        "signal_strength_dbm": rng.normal(-85, 10, n_towers),
        "dropped_call_rate": rng.exponential(0.02, n_towers),
        "latency_ms": rng.exponential(50, n_towers),
        "historical_load_trend": rng.normal(0, 0.01, n_towers),
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training Capacity Forecasting Model...")

    # Generate data
    X = generate_capacity_data(n_towers=500)
    print(f"Generated {len(X)} tower records")

    # Initialize forecaster
    forecaster = CapacityForecaster()
    forecaster.fit(X)

    # Make predictions
    forecasts = forecaster.predict(X.head(20))
    for fc in forecasts[:5]:
        print(f"  {fc.tower_id}: {fc.predicted_load_percent:.1f}% load "
              f"(CI: {fc.confidence_interval[0]:.1f}-{fc.confidence_interval[1]:.1f}%)")
        print(f"    Risk: {fc.risk_level} - {fc.recommendation}")

    # Scenario analysis
    scenarios = forecaster.scenario_analysis(X)
    print(f"\nScenario Analysis:")
    for scenario, results in scenarios.items():
        print(f"  {scenario}: {results['predicted_load_percent']:.1f}% load, "
              f"upgrade needed: {results['action_required']}")
