"""
Finance & Executive Reporting ML Models

Provides machine learning models for:
- Revenue forecasting
- Cost optimization
- Financial anomaly detection
- Executive KPI dashboard
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from datetime import datetime, timedelta


class FinancialMetric(Enum):
    """Financial metric types"""
    REVENUE = "revenue"
    COST = "cost"
    PROFIT = "profit"
    ARPU = "arpu"
    Churn_Rate = "churn_rate"
    CAC = "cac"
    LTV = "ltv"
    EBITDA = "ebitda"


@dataclass
class FinancialForecast:
    """Financial forecast result"""
    metric: FinancialMetric
    forecast_date: str
    predicted_value: float
    confidence_interval: Tuple[float, float]
    trend: str
    risk_level: str
    recommendation: str


class FinancialForecaster:
    """
    Financial forecasting and analysis model.

    Methods:
    - Time series forecasting (moving average, exponential smoothing)
    - Scenario analysis
    - Anomaly detection
    - Executive KPI aggregation
    """

    def __init__(
        self,
        model_dir: str = "ml/finance_reporting",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Forecasting parameters
        self.forecast_horizon_days = 30
        self.smoothing_factor = 0.3

        # Financial baselines
        self.baselines = {}

    def fit(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "value",
        metric_col: str = "metric",
    ):
        """
        Fit financial forecasting model.

        Args:
            df: Historical financial data
            date_col: Column name for date
            value_col: Column name for value
            metric_col: Column name for metric type
        """
        self.history = df.copy()

        # Calculate baselines for each metric
        for metric in df[metric_col].unique():
            metric_data = df[df[metric_col] == metric]
            values = metric_data[value_col].values

            # Calculate baseline metrics
            self.baselines[metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "trend": self._calculate_trend(values),
                "seasonality": self._detect_seasonality(values),
            }

    def forecast(
        self,
        metric: FinancialMetric,
        horizon_days: int = None,
    ) -> FinancialForecast:
        """
        Forecast financial metric.

        Args:
            metric: Financial metric to forecast
            horizon_days: Forecast horizon in days

        Returns:
            FinancialForecast result
        """
        if horizon_days is None:
            horizon_days = self.forecast_horizon_days

        baseline = self.baselines.get(metric.value, {
            "mean": 100000,
            "std": 10000,
            "trend": 0,
            "seasonality": 0,
        })

        # Calculate forecast
        trend_component = baseline["trend"] * horizon_days
        seasonal_component = baseline["seasonality"] * np.sin(2 * np.pi * horizon_days / 30)
        predicted_value = baseline["mean"] + trend_component + seasonal_component

        # Calculate confidence interval
        uncertainty = baseline["std"] * np.sqrt(horizon_days / 30)
        ci_lower = predicted_value - 1.96 * uncertainty
        ci_upper = predicted_value + 1.96 * uncertainty

        # Determine trend direction
        if trend_component > baseline["mean"] * 0.05:
            trend = "increasing"
        elif trend_component < -baseline["mean"] * 0.05:
            trend = "decreasing"
        else:
            trend = "stable"

        # Determine risk level
        risk_score = abs(trend_component) / baseline["mean"]
        if risk_score > 0.2:
            risk_level = "high"
        elif risk_score > 0.1:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate recommendation
        recommendation = self._generate_recommendation(
            metric, predicted_value, trend, risk_level
        )

        return FinancialForecast(
            metric=metric,
            forecast_date=(datetime.now() + timedelta(days=horizon_days)).isoformat(),
            predicted_value=float(predicted_value),
            confidence_interval=(float(ci_lower), float(ci_upper)),
            trend=trend,
            risk_level=risk_level,
            recommendation=recommendation,
        )

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "value",
        metric_col: str = "metric",
        threshold: float = 2.0,
    ) -> List[Dict]:
        """
        Detect financial anomalies.

        Args:
            df: Financial data
            date_col: Column name for date
            value_col: Column name for value
            metric_col: Column name for metric type
            threshold: Z-score threshold for anomaly detection

        Returns:
            List of detected anomalies
        """
        anomalies = []

        for metric in df[metric_col].unique():
            metric_data = df[df[metric_col] == metric].sort_values(date_col)

            if len(metric_data) < 10:
                continue

            values = metric_data[value_col].values
            mean = np.mean(values)
            std = np.std(values)

            if std == 0:
                continue

            # Calculate z-scores
            z_scores = (values - mean) / std

            # Identify anomalies
            for idx, (z_score, value) in enumerate(zip(z_scores, values)):
                if abs(z_score) > threshold:
                    anomalies.append({
                        "date": metric_data.iloc[idx][date_col],
                        "metric": metric,
                        "value": float(value),
                        "z_score": float(z_score),
                        "expected_range": (float(mean - threshold * std), float(mean + threshold * std)),
                        "anomaly_type": "spike" if z_score > 0 else "drop",
                        "severity": "critical" if abs(z_score) > 3 else "warning",
                        "recommendation": self._get_anomaly_recommendation(metric, z_score),
                    })

        return anomalies

    def generate_executive_dashboard(
        self,
        df: pd.DataFrame,
        date_col: str = "date",
        value_col: str = "value",
        metric_col: str = "metric",
    ) -> Dict:
        """
        Generate executive KPI dashboard.

        Args:
            df: Financial data
            date_col: Column name for date
            value_col: Column name for value
            metric_col: Column name for metric type

        Returns:
            Executive dashboard data
        """
        dashboard = {
            "generated_at": datetime.now().isoformat(),
            "kpis": {},
            "trends": {},
            "alerts": [],
            "summary": {},
        }

        # Aggregate KPIs
        for metric in df[metric_col].unique():
            metric_data = df[df[metric_col] == metric]

            # Current period metrics
            current_period = metric_data[metric_data[date_col] >= pd.Timestamp.now() - timedelta(days=30)]
            previous_period = metric_data[
                (metric_data[date_col] >= pd.Timestamp.now() - timedelta(days=60)) &
                (metric_data[date_col] < pd.Timestamp.now() - timedelta(days=30))
            ]

            current_value = current_period[value_col].sum() if len(current_period) > 0 else 0
            previous_value = previous_period[value_col].sum() if len(previous_period) > 0 else 1

            # Calculate change
            change_percent = (current_value - previous_value) / previous_value * 100

            dashboard["kpis"][metric] = {
                "current_value": float(current_value),
                "previous_value": float(previous_value),
                "change_percent": float(change_percent),
                "trend": "up" if change_percent > 0 else "down",
            }

        # Detect anomalies
        anomalies = self.detect_anomalies(df, date_col, value_col, metric_col)
        dashboard["alerts"] = [
            {
                "metric": a["metric"],
                "severity": a["severity"],
                "description": a["recommendation"],
            }
            for a in anomalies[-5:]  # Last 5 anomalies
        ]

        # Generate summary
        total_revenue = dashboard["kpis"].get("revenue", {}).get("current_value", 0)
        total_cost = dashboard["kpis"].get("cost", {}).get("current_value", 0)
        profit = total_revenue - total_cost

        dashboard["summary"] = {
            "total_revenue": float(total_revenue),
            "total_cost": float(total_cost),
            "profit": float(profit),
            "profit_margin": float(profit / total_revenue * 100) if total_revenue > 0 else 0,
            "n_alerts": len(dashboard["alerts"]),
        }

        return dashboard

    def _calculate_trend(self, values: np.ndarray) -> float:
        """Calculate trend component"""
        if len(values) < 2:
            return 0
        return (values[-1] - values[0]) / len(values)

    def _detect_seasonality(self, values: np.ndarray) -> float:
        """Detect seasonality component (simplified)"""
        if len(values) < 7:
            return 0
        # Simple moving average difference
        ma = np.convolve(values, np.ones(7)/7, mode='valid')
        return float(ma[-1] - ma[0]) if len(ma) > 1 else 0

    def _generate_recommendation(
        self,
        metric: FinancialMetric,
        predicted_value: float,
        trend: str,
        risk_level: str,
    ) -> str:
        """Generate financial recommendation"""
        recommendations = {
            FinancialMetric.REVENUE: {
                "increasing": "Revenue growth trend continues. Consider reinvesting in growth initiatives.",
                "decreasing": "Revenue declining. Review pricing strategy and customer retention.",
                "stable": "Revenue stable. Maintain current strategy and monitor for changes.",
            },
            FinancialMetric.COST: {
                "increasing": "Costs rising. Investigate cost drivers and implement efficiency measures.",
                "decreasing": "Cost reduction successful. Sustain current cost management practices.",
                "stable": "Costs stable. Continue monitoring for anomalies.",
            },
            FinancialMetric.PROFIT: {
                "increasing": "Profitability improving. Explore expansion opportunities.",
                "decreasing": "Profit margins压缩. Review cost structure and pricing.",
                "stable": "Profitability stable. Maintain current operational efficiency.",
            },
        }

        metric_recs = recommendations.get(metric, {})
        base_rec = metric_recs.get(trend, "Monitor financial metrics closely.")

        if risk_level == "high":
            return f"HIGH RISK: {base_rec} Immediate review recommended."
        elif risk_level == "medium":
            return f"MEDIUM RISK: {base_rec} Close monitoring advised."
        else:
            return base_rec

    def _get_anomaly_recommendation(self, metric: str, z_score: float) -> str:
        """Get recommendation for detected anomaly"""
        if z_score > 3:
            return f"Critical anomaly detected in {metric}. Immediate investigation required."
        elif z_score > 2:
            return f"Significant anomaly in {metric}. Review recent transactions."
        else:
            return f"Minor deviation in {metric}. Monitor for recurrence."


def generate_financial_data(
    n_days: int = 365,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic financial data"""
    rng = np.random.default_rng(random_state)

    dates = pd.date_range(start="2023-01-01", periods=n_days, freq="D")

    data = []
    for date in dates:
        # Revenue (with seasonal pattern)
        revenue = 100000 + 20000 * np.sin(2 * np.pi * date.dayofyear / 365) + rng.normal(0, 5000)

        # Cost (slightly increasing trend)
        cost = 70000 + 50 * date.dayofyear + rng.normal(0, 3000)

        # Profit (derived)
        profit = revenue - cost

        data.extend([
            {"date": date, "metric": "revenue", "value": max(0, revenue)},
            {"date": date, "metric": "cost", "value": max(0, cost)},
            {"date": date, "metric": "profit", "value": profit},
        ])

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training Financial Forecasting Model...")

    # Generate data
    df = generate_financial_data(n_days=365)
    print(f"Generated {len(df)} financial records")

    # Initialize forecaster
    forecaster = FinancialForecaster()
    forecaster.fit(df)

    # Generate forecasts
    print("\nFinancial Forecasts:")
    for metric in FinancialMetric:
        forecast = forecaster.forecast(metric)
        print(f"  {metric.value}: ${forecast.predicted_value:,.2f} "
              f"(CI: ${forecast.confidence_interval[0]:,.2f} - ${forecast.confidence_interval[1]:,.2f})")
        print(f"    Trend: {forecast.trend}, Risk: {forecast.risk_level}")
        print(f"    {forecast.recommendation}")

    # Generate executive dashboard
    dashboard = forecaster.generate_executive_dashboard(df)
    print(f"\nExecutive Dashboard:")
    print(f"  Total Revenue: ${dashboard['summary']['total_revenue']:,.2f}")
    print(f"  Total Cost: ${dashboard['summary']['total_cost']:,.2f}")
    print(f"  Profit: ${dashboard['summary']['profit']:,.2f}")
    print(f"  Profit Margin: {dashboard['summary']['profit_margin']:.1f}%")
    print(f"  Alerts: {dashboard['summary']['n_alerts']}")
