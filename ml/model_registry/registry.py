"""
ML Model Registry and Versioning

Provides:
- Model versioning and tracking
- Model registration
- Model promotion (dev → staging → prod)
- Model lineage tracking
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class ModelStatus(Enum):
    """Model lifecycle status"""
    DRAFT = "draft"
    TRAINING = "training"
    READY = "ready"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


class ModelStage(Enum):
    """Model deployment stage"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class ModelVersion:
    """Model version metadata"""
    model_id: str
    version: str
    status: ModelStatus
    stage: ModelStage
    created_at: str
    trained_at: str
    metrics: Dict[str, float]
    artifact_path: str
    lineage: Dict[str, str] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)


class ModelRegistry:
    """
    ML model registry for versioning and lifecycle management.

    Features:
    - Model versioning
    - Status tracking
    - Promotion workflow
    - Lineage tracking
    - Performance monitoring
    """

    def __init__(
        self,
        registry_dir: str = "ml/registry",
    ):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

        self.models = {}
        self._load_registry()

    def _load_registry(self):
        """Load registry from disk"""
        registry_file = self.registry_dir / "registry.json"
        if registry_file.exists():
            with open(registry_file, 'r') as f:
                self.models = json.load(f)

    def _save_registry(self):
        """Save registry to disk"""
        registry_file = self.registry_dir / "registry.json"
        with open(registry_file, 'w') as f:
            json.dump(self.models, f, indent=2, default=str)

    def register_model(
        self,
        model_id: str,
        version: str,
        artifact_path: str,
        metrics: Dict[str, float],
        lineage: Dict[str, str] = None,
        metadata: Dict = None,
    ) -> ModelVersion:
        """
        Register a new model version.

        Args:
            model_id: Unique model identifier
            version: Model version string
            artifact_path: Path to model artifact
            metrics: Training metrics
            lineage: Data lineage information
            metadata: Additional metadata

        Returns:
            Registered ModelVersion
        """
        model_key = f"{model_id}:{version}"

        # Check if version already exists
        if model_key in self.models:
            raise ValueError(f"Model version {model_key} already exists")

        # Create model version
        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            status=ModelStatus.DRAFT,
            stage=ModelStage.DEVELOPMENT,
            created_at=datetime.now().isoformat(),
            trained_at=datetime.now().isoformat(),
            metrics=metrics,
            artifact_path=artifact_path,
            lineage=lineage or {},
            metadata=metadata or {},
        )

        # Store in registry
        self.models[model_key] = {
            "model_id": model_version.model_id,
            "version": model_version.version,
            "status": model_version.status.value,
            "stage": model_version.stage.value,
            "created_at": model_version.created_at,
            "trained_at": model_version.trained_at,
            "metrics": model_version.metrics,
            "artifact_path": model_version.artifact_path,
            "lineage": model_version.lineage,
            "metadata": model_version.metadata,
        }

        self._save_registry()

        return model_version

    def promote_model(
        self,
        model_id: str,
        from_stage: ModelStage,
        to_stage: ModelStage,
        required_metrics: Dict[str, float] = None,
    ) -> ModelVersion:
        """
        Promote model to next stage.

        Args:
            model_id: Model identifier
            from_stage: Current stage
            to_stage: Target stage
            required_metrics: Minimum metric thresholds

        Returns:
            Promoted ModelVersion
        """
        # Find latest version in current stage
        latest_version = self._get_latest_version(model_id, from_stage)
        if latest_version is None:
            raise ValueError(f"No model found in {from_stage.value} stage")

        # Check required metrics
        if required_metrics:
            for metric, threshold in required_metrics.items():
                current_value = latest_version.metrics.get(metric, 0)
                if current_value < threshold:
                    raise ValueError(
                        f"Metric {metric}={current_value:.4f} below threshold {threshold:.4f}"
                    )

        # Update stage and status
        latest_version.stage = to_stage
        latest_version.status = ModelStatus.READY if to_stage == ModelStage.STAGING else ModelStatus.PRODUCTION

        # Update registry
        model_key = f"{model_id}:{latest_version.version}"
        self.models[model_key]["stage"] = to_stage.value
        self.models[model_key]["status"] = latest_version.status.value

        self._save_registry()

        return latest_version

    def _get_latest_version(
        self,
        model_id: str,
        stage: ModelStage,
    ) -> Optional[ModelVersion]:
        """Get latest model version for given stage"""
        candidates = []
        for key, data in self.models.items():
            if data["model_id"] == model_id and data["stage"] == stage.value:
                candidates.append(ModelVersion(**data))

        if not candidates:
            return None

        # Sort by trained_at and return latest
        candidates.sort(key=lambda x: x.trained_at, reverse=True)
        return candidates[0]

    def get_model(self, model_id: str, version: str = None) -> Optional[ModelVersion]:
        """
        Get model by ID and optional version.

        Args:
            model_id: Model identifier
            version: Optional version (default: latest)

        Returns:
            ModelVersion or None
        """
        if version:
            key = f"{model_id}:{version}"
            if key in self.models:
                return ModelVersion(**self.models[key])
        else:
            # Get latest version
            return self._get_latest_version(model_id, ModelStage.PRODUCTION) or \
                   self._get_latest_version(model_id, ModelStage.STAGING) or \
                   self._get_latest_version(model_id, ModelStage.DEVELOPMENT)

        return None

    def list_models(
        self,
        model_id: str = None,
        stage: ModelStage = None,
        status: ModelStatus = None,
    ) -> List[ModelVersion]:
        """
        List models with optional filters.

        Args:
            model_id: Optional model ID filter
            stage: Optional stage filter
            status: Optional status filter

        Returns:
            List of ModelVersions
        """
        results = []
        for key, data in self.models.items():
            if model_id and data["model_id"] != model_id:
                continue
            if stage and data["stage"] != stage.value:
                continue
            if status and data["status"] != status.value:
                continue
            results.append(ModelVersion(**data))

        return results

    def get_model_lineage(self, model_id: str, version: str) -> Dict:
        """
        Get full lineage for a model version.

        Args:
            model_id: Model identifier
            version: Model version

        Returns:
            Lineage information
        """
        key = f"{model_id}:{version}"
        if key not in self.models:
            return {}

        model = ModelVersion(**self.models[key])
        return {
            "model_id": model.model_id,
            "version": model.version,
            "created_at": model.created_at,
            "trained_at": model.trained_at,
            "training_data": model.lineage.get("training_data", "unknown"),
            "feature_set": model.lineage.get("feature_set", "unknown"),
            "hyperparameters": model.lineage.get("hyperparameters", {}),
            "parent_models": model.lineage.get("parent_models", []),
            "downstream_models": model.lineage.get("downstream_models", []),
        }


if __name__ == "__main__":
    # Example usage
    print("Testing Model Registry...")

    # Initialize registry
    registry = ModelRegistry()

    # Register models
    model1 = registry.register_model(
        model_id="churn_predictor",
        version="1.0.0",
        artifact_path="ml/churn_model/model_v1.pkl",
        metrics={"roc_auc": 0.85, "accuracy": 0.82, "f1_score": 0.80},
        lineage={
            "training_data": "data/training/cdr_2024.csv",
            "feature_set": "feature_engineering_v1",
            "hyperparameters": {"n_estimators": 100, "max_depth": 5},
        },
    )
    print(f"Registered: {model1.model_id}:{model1.version}")

    model2 = registry.register_model(
        model_id="churn_predictor",
        version="1.1.0",
        artifact_path="ml/churn_model/model_v2.pkl",
        metrics={"roc_auc": 0.88, "accuracy": 0.85, "f1_score": 0.83},
        lineage={
            "training_data": "data/training/cdr_2024_v2.csv",
            "feature_set": "feature_engineering_v2",
            "hyperparameters": {"n_estimators": 150, "max_depth": 6},
            "parent_models": ["churn_predictor:1.0.0"],
        },
    )
    print(f"Registered: {model2.model_id}:{model2.version}")

    # Promote to staging
    promoted = registry.promote_model(
        model_id="churn_predictor",
        from_stage=ModelStage.DEVELOPMENT,
        to_stage=ModelStage.STAGING,
        required_metrics={"roc_auc": 0.85},
    )
    print(f"Promoted to staging: {promoted.model_id}:{promoted.version}")

    # List models
    models = registry.list_models(model_id="churn_predictor")
    print(f"\nModel versions:")
    for m in models:
        print(f"  {m.model_id}:{m.version} - {m.status.value} ({m.stage.value})")

    # Get lineage
    lineage = registry.get_model_lineage("churn_predictor", "1.1.0")
    print(f"\nLineage for 1.1.0:")
    print(f"  Training data: {lineage['training_data']}")
    print(f"  Parent models: {lineage['parent_models']}")
