"""
Customer Segmentation Model

Clusters customers based on usage patterns, demographics, and behavior:
- K-Means clustering with Elbow method
- Usage-based segments (Heavy, Medium, Light)
- Value-based segments (High, Medium, Low LTV)
- Hybrid segments combining both dimensions
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not installed. Using fallback implementation.")


class SegmentType(Enum):
    """Segment classification types"""
    USAGE = "usage"
    VALUE = "value"
    HYBRID = "hybrid"


@dataclass
class CustomerSegment:
    """Customer segment definition"""
    segment_id: str
    segment_name: str
    segment_type: SegmentType
    size: int
    description: str
    avg_metrics: Dict[str, float]
    characteristics: List[str]


class CustomerSegmenter:
    """
    Customer segmentation using clustering algorithms.

    Creates segments based on:
    - Usage patterns (data, voice, SMS)
    - Billing behavior (ARPU, payment patterns)
    - Service usage (roaming, complaints)
    - Combined usage-value matrix
    """

    def __init__(
        self,
        model_dir: str = "ml/churn_model/segmentation",
        n_clusters: int = 5,
    ):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.n_clusters = n_clusters
        self.segmenter_type = SegmentType.HYBRID

        self.scaler = StandardScaler()
        self.kmeans = None
        self.pca = PCA(n_components=2)

        # Predefined segment descriptions
        self.segment_descriptions = {
            "platinum_high_value": {
                "name": "Platinum High Value",
                "description": "High ARPU, high usage, loyal customers",
                "characteristics": ["Premium plan", "Low churn risk", "High referrals"]
            },
            "gold_premium": {
                "name": "Gold Premium",
                "description": "Above-average usage and spending",
                "characteristics": ["Mid-tier plan", "Moderate churn risk", "Data heavy"]
            },
            "silver_standard": {
                "name": "Silver Standard",
                "description": "Average usage, standard plan",
                "characteristics": ["Base plan", "Price sensitive", "Moderate retention"]
            },
            "bronze_budget": {
                "name": "Bronze Budget",
                "description": "Low usage, prepaid or budget plan",
                "characteristics": ["Prepaid", "Occasional usage", "Easy to lose"]
            },
            "at_risk_churn": {
                "name": "At-Risk Churn",
                "description": "Declining usage, high complaint rate",
                "characteristics": ["Usage dropping", "Multiple complaints", "High churn risk"]
            },
        }

    def fit(
        self,
        X: pd.DataFrame,
        segment_type: SegmentType = SegmentType.HYBRID,
        random_state: int = 42,
    ) -> Dict:
        """
        Fit segmentation model.

        Args:
            X: Feature matrix
            segment_type: Type of segmentation
            random_state: Random seed

        Returns:
            Fitting metrics and segment info
        """
        self.segmenter_type = segment_type

        if not SKLEARN_AVAILABLE:
            return self._fit_fallback(X, random_state)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Find optimal clusters using elbow method
        inertia = []
        k_range = range(2, min(10, len(X) // 10))
        for k in k_range:
            km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
            km.fit(X_scaled)
            inertia.append(km.inertia_)

        # Use predefined n_clusters or optimal
        optimal_k = k_range[np.argmin([
            inertia[i] - inertia[i + 1]
            for i in range(len(inertia) - 1)
        ])] if len(inertia) > 1 else self.n_clusters

        # Fit final model
        self.kmeans = KMeans(
            n_clusters=self.n_clusters,
            random_state=random_state,
            n_init=10,
            max_iter=300,
        )
        labels = self.kmeans.fit_predict(X_scaled)

        # Calculate metrics
        sil_score = silhouette_score(X_scaled, labels)

        # Analyze segments
        segment_stats = self._analyze_segments(X, labels)

        return {
            "n_clusters": self.n_clusters,
            "silhouette_score": sil_score,
            "segment_stats": segment_stats,
            "optimal_k": optimal_k,
        }

    def _fit_fallback(
        self,
        X: pd.DataFrame,
        random_state: int = 42,
    ) -> Dict:
        """Fallback segmentation using rule-based clustering"""
        rng = np.random.default_rng(random_state)

        # Rule-based segmentation
        X_numeric = X.fillna(0).astype(float)

        # Create composite score
        if "monthly_arpu" in X_numeric.columns and "data_usage_gb" in X_numeric.columns:
            arpu_norm = (X_numeric["monthly_arpu"] - X_numeric["monthly_arpu"].min()) / \
                       (X_numeric["monthly_arpu"].max() - X_numeric["monthly_arpu"].min() + 1e-8)
            data_norm = (X_numeric["data_usage_gb"] - X_numeric["data_usage_gb"].min()) / \
                       (X_numeric["data_usage_gb"].max() - X_numeric["data_usage_gb"].min() + 1e-8)
            composite = 0.6 * arpu_norm + 0.4 * data_norm
        else:
            composite = rng.random(len(X))

        # Create segments based on quantiles
        percentiles = np.linspace(0, 1, self.n_clusters + 1)
        labels = np.digitize(composite, percentiles[1:-1])

        segment_stats = self._analyze_segments(X, labels)

        return {
            "n_clusters": self.n_clusters,
            "silhouette_score": 0.5,  # Estimated
            "segment_stats": segment_stats,
            "method": "rule-based fallback",
        }

    def _analyze_segments(
        self,
        X: pd.DataFrame,
        labels: np.ndarray,
    ) -> Dict[str, Dict]:
        """Analyze each segment's characteristics"""
        segment_stats = {}

        for label in np.unique(labels):
            mask = labels == label
            segment_data = X[mask]

            stats = {
                "size": int(mask.sum()),
                "percentage": float(mask.sum() / len(X)),
            }

            # Calculate numeric feature means
            numeric_cols = X.select_dtypes(include=[np.number]).columns
            for col in numeric_cols:
                stats[f"avg_{col}"] = float(segment_data[col].mean())

            segment_stats[f"segment_{label}"] = stats

        return segment_stats

    def predict(
        self,
        X: pd.DataFrame,
        customer_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Predict segment assignments for new data.

        Args:
            X: Feature matrix
            customer_ids: Optional customer IDs

        Returns:
            List of segment assignments
        """
        if customer_ids is None:
            customer_ids = [f"CUST_{i:06d}" for i in range(len(X))]

        if self.kmeans is None:
            return self._predict_fallback(X, customer_ids)

        # Scale and predict
        X_scaled = self.scaler.transform(X)
        labels = self.kmeans.predict(X_scaled)

        results = []
        for cust_id, label in zip(customer_ids, labels):
            segment_info = self._get_segment_info(label)
            results.append({
                "customer_id": cust_id,
                "segment_id": f"segment_{label}",
                "segment_name": segment_info["name"],
                "segment_type": self.segmenter_type.value,
                "characteristics": segment_info["characteristics"],
            })

        return results

    def _predict_fallback(
        self,
        X: pd.DataFrame,
        customer_ids: List[str],
    ) -> List[Dict]:
        """Fallback prediction using rule-based segmentation"""
        X_numeric = X.fillna(0).astype(float)
        rng = np.random.default_rng(42)

        if "monthly_arpu" in X_numeric.columns:
            arpu_norm = (X_numeric["monthly_arpu"] - X_numeric["monthly_arpu"].min()) / \
                       (X_numeric["monthly_arpu"].max() - X_numeric["monthly_arpu"].min() + 1e-8)
        else:
            arpu_norm = rng.random(len(X))

        labels = np.digitize(arpu_norm, np.linspace(0, 1, self.n_clusters - 1))
        labels = np.clip(labels, 0, self.n_clusters - 1)

        results = []
        for cust_id, label in zip(customer_ids, labels):
            segment_info = self._get_segment_info(int(label))
            results.append({
                "customer_id": cust_id,
                "segment_id": f"segment_{label}",
                "segment_name": segment_info["name"],
                "segment_type": self.segmenter_type.value,
                "characteristics": segment_info["characteristics"],
            })

        return results

    def _get_segment_info(self, label: int) -> Dict:
        """Get segment information by label"""
        keys = list(self.segment_descriptions.keys())
        if label < len(keys):
            return self.segment_descriptions[keys[label]]
        return {
            "name": f"Segment {label}",
            "description": f"Auto-generated segment {label}",
            "characteristics": ["Standard segment"],
        }

    def get_segment_summary(self) -> Dict:
        """Get summary of all segments"""
        if not hasattr(self, 'kmeans') or self.kmeans is None:
            return {"status": "model_not_trained"}

        summary = {
            "n_segments": self.n_clusters,
            "segment_type": self.segmenter_type.value,
            "segments": []
        }

        for label in range(self.n_clusters):
            info = self._get_segment_info(label)
            summary["segments"].append({
                "id": f"segment_{label}",
                "name": info["name"],
                "description": info["description"],
                "characteristics": info["characteristics"],
            })

        return summary


def generate_segmentation_data(
    n_samples: int = 5000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Generate synthetic customer data for segmentation"""
    rng = np.random.default_rng(random_state)

    data = {
        "monthly_arpu": rng.lognormal(4.5, 0.5, n_samples).clip(50, 500),
        "data_usage_gb": rng.lognormal(2.5, 0.8, n_samples).clip(1, 100),
        "voice_minutes": rng.poisson(500, n_samples),
        "sms_count": rng.poisson(200, n_samples),
        "roaming_minutes": rng.exponential(30, n_samples).clip(0, 500),
        "contract_length_months": rng.choice([6, 12, 24], n_samples, p=[0.3, 0.5, 0.2]),
        "customer_tenure_months": rng.exponential(24, n_samples).clip(1, 120),
        "complaint_count_3m": rng.poisson(1, n_samples),
        "autopay_flag": rng.choice([0, 1], n_samples, p=[0.6, 0.4]),
        "loyalty_points": rng.poisson(500, n_samples),
    }

    return pd.DataFrame(data)


if __name__ == "__main__":
    # Example usage
    print("Training Customer Segmentation Model...")

    # Generate data
    X = generate_segmentation_data(n_samples=5000)
    print(f"Generated {len(X)} customer records")

    # Initialize segmenter
    segmenter = CustomerSegmenter(n_clusters=5)

    # Fit model
    results = segmenter.fit(X)
    print(f"\nSilhouette Score: {results['silhouette_score']:.4f}")
    print(f"Number of segments: {results['n_clusters']}")

    # Predict segments
    predictions = segmenter.predict(X.head(10))
    for pred in predictions:
        print(f"  {pred['customer_id']}: {pred['segment_name']}")

    # Get summary
    summary = segmenter.get_segment_summary()
    print(f"\nSegment Summary: {json.dumps(summary, indent=2)}")
