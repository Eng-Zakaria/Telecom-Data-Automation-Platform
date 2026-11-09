"""
ML Package __init__.py

Provides unified imports for all ML models.
"""

# Customer & Retention Models
from .churn_model import (
    ChurnPredictor,
    ChurnHorizon,
    CustomerSegmenter,
    SegmentType,
    CLVModel,
    NextBestActionEngine,
    generate_synthetic_training_data,
    generate_segmentation_data,
    generate_clv_data,
    generate_nba_data,
)

# Fraud Detection Models
from .fraud_detection import (
    FraudDetector,
    FraudType,
    FraudSeverity,
    RevenueLeakageDetector,
    LeakageType,
    generate_fraud_data,
    generate_leakage_data,
)

# Network Operations Models
from .network_failure_prediction import (
    NetworkFailurePredictor,
    FailureType,
    PredictionHorizon,
    CapacityForecaster,
    generate_network_kpi_data,
    generate_capacity_data,
)

# Marketing & Sales Models
from .propensity_model import (
    PropensityPredictor,
    PropensityType,
    CampaignOptimizer,
    generate_propensity_data,
    generate_campaign_data,
)

# Pricing Elasticity
from .pricing_elasticity import (
    PricingElasticityModel,
    ElasticityResult,
    generate_elasticity_data,
)

# Roaming Optimization
from .roaming_optimization.roaming_model import (
    RoamingOptimizationModel,
    SettlementIssue,
    PartnerPerformance,
    generate_roaming_data,
)

# Finance & Executive Reporting
from .finance_reporting.forecaster import (
    FinancialForecaster,
    FinancialMetric,
    generate_financial_data,
)

# MLOps Components
from .model_registry.registry import (
    ModelRegistry,
    ModelVersion,
    ModelStatus,
    ModelStage,
)

from .pipeline_orchestrator.orchestrator import (
    MLPipelineOrchestrator,
    PipelineStatus,
    PipelineRun,
)

__version__ = "1.0.0"

__all__ = [
    # Customer & Retention
    "ChurnPredictor",
    "ChurnHorizon",
    "CustomerSegmenter",
    "SegmentType",
    "CLVModel",
    "NextBestActionEngine",
    "generate_synthetic_training_data",
    "generate_segmentation_data",
    "generate_clv_data",
    "generate_nba_data",

    # Fraud Detection
    "FraudDetector",
    "FraudType",
    "FraudSeverity",
    "RevenueLeakageDetector",
    "LeakageType",
    "generate_fraud_data",
    "generate_leakage_data",

    # Network Operations
    "NetworkFailurePredictor",
    "FailureType",
    "PredictionHorizon",
    "CapacityForecaster",
    "generate_network_kpi_data",
    "generate_capacity_data",

    # Marketing & Sales
    "PropensityPredictor",
    "PropensityType",
    "CampaignOptimizer",
    "generate_propensity_data",
    "generate_campaign_data",

    # Pricing Elasticity
    "PricingElasticityModel",
    "ElasticityResult",
    "generate_elasticity_data",

    # Roaming Optimization
    "RoamingOptimizationModel",
    "SettlementIssue",
    "PartnerPerformance",
    "generate_roaming_data",

    # Finance & Executive
    "FinancialForecaster",
    "FinancialMetric",
    "generate_financial_data",

    # MLOps
    "ModelRegistry",
    "ModelVersion",
    "ModelStatus",
    "ModelStage",
    "MLPipelineOrchestrator",
    "PipelineStatus",
    "PipelineRun",
]
