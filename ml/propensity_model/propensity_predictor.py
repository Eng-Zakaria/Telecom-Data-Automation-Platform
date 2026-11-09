"""
Propensity Model for Marketing & Sales

Predicts customer likelihood to:
- Upgrade plan
- Add data bundle
- Switch to VoLTE
- Subscribe to streaming
- Refer friend
- Accept promotion
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Using fallback implementation.")


class PropensityType(Enum):
    """Propensity prediction types"""
    UPGRADE_PLAN = "upgrade_plan"
    ADD_DATA_BUNDLE = "add_data_bundle"
    SWITCH_VOLTTE = "switch_volte"
    SUBSCRIBE_STREAMING = "subscribe_streaming"
    REFER_FRIEND = "refer_friend"
    ACCEPT_PROMOTION = "accept_promotion"
    TRY_NEW_PRODUCT = "try_new_product"


@dataclass
class PropensityPrediction:
    """Propensity prediction result"""
    customer_id: str
    propensity_type: PropensityType
    probability: float
    confidence: float
    top_factors: List[Tuple[str, float]]
    recommended_action: str
    optimal_channel: str
    timestamp: str


class PropensityPredictor:
    """
    Customer propensity prediction model.

    Predicts likelihood of various marketing actions:
    - Plan upgrades
    - Product additions
    - Service switches
    - Referrals
    - Promotion acceptance
    """

    def __init__(
        self,
        model_dir: str = "ml/propensity_model",
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.models = {}
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None

        # Feature definitions
        self.feature_names = [
            "monthly_arpu",
            "data_usage_gb",
            "voice_minutes",
            "sms_count",
            "roaming_minutes",
            "contract_length_months",
            "customer_tenure_months",
            "complaint_count_3m",
            "support_ticket_count",
            "payment_delay_days",
            "autopay_flag",
            "loyalty_points",
            "referred_customers",
            "device_type",  # 0=feature, 1=smartphone, 2=flagship
            "age_group",
            "region_code",
        ]

        # Action-specific feature importance weights
        self.action_weights = {
            PropensityType.UPGRADE_PLAN: {
                "monthly_arpu": 0.2,
                "data_usage_gb": 0.15,
                "contract_length_months": 0.15,
                "device_type": 0.1,
                "loyalty_points": 0.1,
            },
            PropensityType.ADD_DATA_BUNDLE: {
                "data_usage_gb": 0.3,
                "monthly_arpu": 0.15,
                "contract_length_months": 0.1,
                "roaming_minutes": 0.1,
            },
            PropensityType.SUBSCRIBE_STREAMING: {
                "age_group": 0.2,
                "data_usage_gb": 0.2,
                "monthly_arpu": 0.15,
                "device_type": 0.15,
                "sms_count": 0.1,
            },
            PropensityType.REFER_FRIEND: {
                "loyalty_points": 0.25,
                "customer_tenure_months": 0.2,
                "complaint_count_3m": 0.15,
                "referred_customers": 0.15,
                "monthly_arpu": 0.1,
            },
        }

    def train(
        self,
        X: pd.DataFrame,
        y_dict: Dict[PropensityType, pd.Series],
    ) -> Dict:
        """
        Train propensity models for all types.

        Args:
            X: Feature matrix
            y_dict: Dictionary of labels for each propensity type

        Returns:
            Training metrics for each type
        """
        results = {}

        for propensity_type, y in y_dict.items():
            if not SKLEARN_AVAILABLE:
                results[propensity_type.value] = {
                    "status": "sklearn_not_available",
                    "method": "fallback",
                }
                continue

            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train classifier
            model = GradientBoostingClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                random_state=42,
            )
            model.fit(X_scaled, y)

            # Evaluate
            from sklearn.metrics import roc_auc_score
            y_pred = model.predict(X_scaled)
            y_prob = model.predict_proba(X_scaled)[:, 1]

            metrics = {
                "roc_auc": roc_auc_score(y, y_prob),
                "accuracy": (y_pred == y).mean(),
                "feature_importances": dict(
                    zip(X.columns.tolist(), model.feature_importances_.tolist())
                ),
            }

            self.models[propensity_type.value] = model
            results[propensity_type.value] = metrics

        return results

    def predict(
        self,
        X: pd.DataFrame,
        customer_ids: Optional[List[str]] = None,
        propensity_types: Optional[List[PropensityType]] = None,
    ) -> List[PropensityPrediction]:
        """
        Predict propensities for customers.

        Args:
            X: Feature matrix
            customer_ids: Optional customer IDs
            propensity_types: Types to predict (default: all)

        Returns:
            List of PropensityPrediction objects
        """
        if customer_ids is None:
            customer_ids = [f"CUST_{i:06d}" for i in range(len(X))]

        if propensity_types is None:
            propensity_types = list(PropensityType)

        predictions = []

        for idx, row in X.iterrows():
            for propensity_type in propensity_types:
                # Get probability
                if propensity_type.value in self.models:
                    X_scaled = self.scaler.transform(X.iloc[idx:idx+1])
                    prob = self.models[propensity_type.value].predict_proba(X_scaled)[0, 1]
                    feature_importance = self.models[propensity_type.value].feature_importances_
                else:
                    # Fallback: use weighted combination
                    prob = self._calculate_fallback_probability(row, propensity_type)
                    feature_importance = self._get_fallback_importance(propensity_type)

                # Get top factors
                top_factors = self._get_top_factors(row, feature_importance, X.columns)

                # Get recommended action
                recommended_action = self._get_recommended_action(propensity_type, prob)

                # Get optimal channel
                optimal_channel = self._get_optimal_channel(row, propensity_type)

                predictions.append(PropensityPrediction(
                    customer_id=customer_ids[idx],
                    propensity_type=propensity_type,
                    probability=float(prob),
                    confidence=float(prob),
                    top_factors=top_factors,
                    recommended_action=recommended_action,
                    optimal_channel=optimal_channel,
                    timestamp=pd.Timestamp.now().isoformat(),
                ))

        return predictions

    def _calculate_fallback_probability(
        self,
        row: pd.Series,
        propensity_type: PropensityType,
    ) -> float:
        """Calculate fallback propensity probability"""
        weights = self.action_weights.get(propensity_type, {})
        if not weights:
            return 0.3  # Default probability

        prob = 0.2  # Base probability
        for feature, weight in weights.items():
            if feature in row.index:
                # Normalize feature value to 0-1 range
                value = row[feature]
                if isinstance(value, (int, float)):
                    normalized = min(1.0, max(0.0, value / 100))
                    prob += weight * normalized

        return min(1.0, prob)

    def _get_fallback_importance(
        self,
        propensity_type: PropensityType,
    ) -> np.ndarray:
        """Get fallback feature importance"""
        weights = self.action_weights.get(propensity_type, {})
        importance = np.zeros(len(self.feature_names))

        for i, feature in enumerate(self.feature_names):
            if feature in weights:
                importance[i] = weights[feature]

        # Normalize
        if importance.sum() > 0:
            importance = importance / importance.sum()

        return importance

    def _get_top_factors(
        self,
        row: pd.Series,
        importance: np.ndarray,
        feature_names: pd.Index,
    ) -> List[Tuple[str, float]]:
        """Get top contributing factors"""
        factors = []
        for idx in np.argsort(importance)[-3:][::-1]:
            if idx < len(feature_names):
                feature = feature_names[idx]
                if feature in row.index:
                    factors.append((feature, float(importance[idx])))
        return factors

    def _get_recommended_action(
        self,
        propensity_type: PropensityType,
        probability: float,
    ) -> str:
        """Get recommended marketing action"""
        actions = {
            PropensityType.UPGRADE_PLAN: "Offer premium plan with upgrade discount",
            PropensityType.ADD_DATA_BUNDLE: "Promote additional data bundle",
            PropensityType.SUBSCRIBE_STREAMING: "Offer streaming service bundle",
            PropensityType.REFER_FRIEND: "Launch referral campaign with rewards",
            PropensityType.SWITCH_VOLTTE: "Promote VoLTE upgrade benefits",
            PropensityType.ACCEPT_PROMOTION: "Send personalized promotion offer",
            PropensityType.TRY_NEW_PRODUCT: "Introduce new product with trial",
        }
        base_action = actions.get(propensity_type, "Send targeted offer")

        if probability > 0.7:
            return f"Immediate: {base_action}. High conversion expected."
        elif probability > 0.4:
            return f"Schedule: {base_action}. Medium conversion expected."
        else:
            return f"Nurture: {base_action}. Monitor and re-engage later."

    def _get_optimal_channel(
        self,
        row: pd.Series,
        propensity_type: PropensityType,
    ) -> str:
        """Determine optimal marketing channel"""
        # Channel preference based on customer attributes
        channels = []

        if row.get("age_group", 2) <= 2:
            channels.append("sms")
            channels.append("whatsapp")

        if row.get("device_type", 0) >= 1:
            channels.append("push_notification")
            channels.append("email")

        if row.get("monthly_arpu", 100) > 150:
            channels.append("phone_call")
            channels.append("personal_email")

        # Default channels
        if not channels:
            channels = ["sms", "email"]

        return channels[0]  # Return primary channel

    def get_campaign_recommendations(
        self,
        predictions: List[PropensityPrediction],
        min_probability: float = 0.5,
    ) -> Dict:
        """Generate campaign recommendations from predictions"""
        campaigns = {}

        for pred in predictions:
            if pred.probability >= min_probability:
                ptype = pred.propensity_type.value
                if ptype not in campaigns:
                    campaigns[ptype] = {
                        "propensity_type": ptype,
                        "eligible_customers": [],
                        "avg_probability": 0,
                        "recommended_actions": [],
                    }

                campaigns[ptype]["eligible_customers"].append({
                    "customer_id": pred.customer_id,
                    "probability": pred.probability,
                    "optimal_channel": pred.optimal_channel,
                })
                campaigns[ptype]["recommended_actions"].append(pred.recommended_action)

        # Calculate averages
        for ptype, campaign in campaigns.items():
            if campaign["eligible_customers"]:
                campaign["avg_probability"] = np.mean([
                    c["probability"] for c in campaign["eligible_customers"]
                ])
                campaign["eligible_count"] = len(campaign["eligible_customers"])
                # Deduplicate actions
                campaign["recommended_actions"] = list(set(campaign["recommended_actions"]))

        return campaigns


def generate_propensity_data(
    n_samples: int = 5000,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, Dict[PropensityType, pd.Series]]:
    """Generate synthetic propensity data"""
    rng = np.random.default_rng(random_state)

    # Generate features
    data = {
        "monthly_arpu": rng.lognormal(4.5, 0.5, n_samples).clip(50, 500),
        "data_usage_gb": rng.lognormal(2.5, 0.8, n_samples).clip(1, 100),
        "voice_minutes": rng.poisson(500, n_samples),
        "sms_count": rng.poisson(200, n_samples),
        "roaming_minutes": rng.exponential(30, n_samples).clip(0, 500),
        "contract_length_months": rng.choice([6, 12, 24], n_samples, p=[0.3, 0.5, 0.2]),
        "customer_tenure_months": rng.exponential(24, n_samples).clip(1, 120),
        "complaint_count_3m": rng.poisson(1, n_samples),
        "support_ticket_count": rng.poisson(0.5, n_samples),
        "payment_delay_days": rng.poisson(2, n_samples),
        "autopay_flag": rng.choice([0, 1], n_samples, p=[0.6, 0.4]),
        "loyalty_points": rng.poisson(500, n_samples),
        "referred_customers": rng.poisson(0.3, n_samples),
        "device_type": rng.choice([0, 1, 2], n_samples, p=[0.3, 0.5, 0.2]),
        "age_group": rng.choice([0, 1, 2, 3, 4], n_samples),
        "region_code": rng.integers(0, 11, n_samples),
    }

    df = pd.DataFrame(data)

    # Generate labels based on features
    y_dict = {}

    # Upgrade plan propensity
    upgrade_score = (
        df["monthly_arpu"] / 500 * 0.3 +
        df["contract_length_months"] / 24 * 0.2 +
        df["device_type"] / 2 * 0.2 +
        df["loyalty_points"] / 1000 * 0.15 +
        rng.normal(0, 0.1, n_samples)
    )
    y_dict[PropensityType.UPGRADE_PLAN] = (upgrade_score > 0.5).astype(int)

    # Data bundle propensity
    data_score = (
        df["data_usage_gb"] / 100 * 0.4 +
        df["monthly_arpu"] / 500 * 0.2 +
        df["roaming_minutes"] / 500 * 0.2 +
        rng.normal(0, 0.1, n_samples)
    )
    y_dict[PropensityType.ADD_DATA_BUNDLE] = (data_score > 0.5).astype(int)

    # Streaming subscription propensity
    streaming_score = (
        (4 - df["age_group"]) / 4 * 0.3 +
        df["data_usage_gb"] / 100 * 0.25 +
        df["device_type"] / 2 * 0.25 +
        rng.normal(0, 0.1, n_samples)
    )
    y_dict[PropensityType.SUBSCRIBE_STREAMING] = (streaming_score > 0.5).astype(int)

    # Refer friend propensity
    refer_score = (
        df["loyalty_points"] / 1000 * 0.3 +
        df["customer_tenure_months"] / 120 * 0.25 +
        (1 - df["complaint_count_3m"] / 10) * 0.25 +
        rng.normal(0, 0.1, n_samples)
    )
    y_dict[PropensityType.REFER_FRIEND] = (refer_score > 0.5).astype(int)

    return df, y_dict


if __name__ == "__main__":
    # Example usage
    print("Training Propensity Prediction Model...")

    # Generate data
    X, y_dict = generate_propensity_data(n_samples=5000)
    print(f"Generated {len(X)} customer records")

    # Initialize predictor
    predictor = PropensityPredictor()

    # Train models
    results = predictor.train(X, y_dict)
    for ptype, metrics in results.items():
        print(f"\n{ptype}:")
        print(f"  ROC-AUC: {metrics.get('roc_auc', 'N/A')}")
        print(f"  Accuracy: {metrics.get('accuracy', 'N/A')}")

    # Make predictions
    predictions = predictor.predict(X.head(20))
    print(f"\nPredictions for 20 customers:")
    for pred in predictions[:10]:
        print(f"  {pred.customer_id}: {pred.propensity_type.value} = "
              f"{pred.probability:.2%} ({pred.optimal_channel})")

    # Get campaign recommendations
    campaigns = predictor.get_campaign_recommendations(predictions, min_probability=0.4)
    print(f"\nCampaign Recommendations:")
    for ptype, campaign in campaigns.items():
        if campaign.get("eligible_count", 0) > 0:
            print(f"  {ptype}: {campaign['eligible_count']} customers, "
                  f"avg prob={campaign['avg_probability']:.2%}")
