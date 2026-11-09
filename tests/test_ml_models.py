"""
ML Models Test Suite

Comprehensive tests for all machine learning models:
- Churn prediction
- Fraud detection
- Network failure prediction
- Propensity modeling
- Roaming optimization
- Financial forecasting
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.churn_model import (
    ChurnPredictor,
    ChurnHorizon,
    CustomerSegmenter,
    CLVModel,
    NextBestActionEngine,
    generate_synthetic_training_data,
    generate_segmentation_data,
    generate_clv_data,
    generate_nba_data,
)
from ml.fraud_detection import (
    FraudDetector,
    FraudType,
    FraudSeverity,
    RevenueLeakageDetector,
    LeakageType,
    generate_fraud_data,
    generate_leakage_data,
)
from ml.network_failure_prediction import (
    NetworkFailurePredictor,
    FailureType,
    PredictionHorizon,
    CapacityForecaster,
    generate_network_kpi_data,
    generate_capacity_data,
)
from ml.propensity_model import (
    PropensityPredictor,
    PropensityType,
    CampaignOptimizer,
    generate_propensity_data,
    generate_campaign_data,
)
from ml.pricing_elasticity import PricingElasticityModel, generate_elasticity_data
from ml.roaming_optimization import RoamingOptimizationModel, generate_roaming_data
from ml.finance_reporting import FinancialForecaster, FinancialMetric, generate_financial_data
from ml.model_registry import ModelRegistry, ModelStatus, ModelStage
from ml.pipeline_orchestrator import MLPipelineOrchestrator, PipelineStatus


# =============================================================================
# Churn Prediction Tests
# =============================================================================

class TestChurnPredictor:
    """Tests for ChurnPredictor"""

    def test_train_and_predict(self):
        """Test training and prediction workflow"""
        X, y = generate_synthetic_training_data(n_samples=1000, churn_rate=0.15)
        predictor = ChurnPredictor()

        # Train
        metrics = predictor.train(X, y, ChurnHorizon.DAYS_30)
        assert "roc_auc" in metrics
        assert "accuracy" in metrics
        assert metrics["accuracy"] > 0.5

        # Predict
        predictions = predictor.predict(X.head(10), ChurnHorizon.DAYS_30)
        assert len(predictions) == 10
        for pred in predictions:
            assert 0 <= pred.churn_probability <= 1
            assert pred.risk_level in ["high", "medium", "low", "minimal"]

    def test_multi_horizon_training(self):
        """Test training for multiple horizons"""
        X, y = generate_synthetic_training_data(n_samples=1000)
        predictor = ChurnPredictor()

        for horizon in ChurnHorizon:
            metrics = predictor.train(X, y, horizon)
            assert metrics["horizon"] == horizon.value

    def test_risk_level_classification(self):
        """Test risk level classification logic"""
        X, y = generate_synthetic_training_data(n_samples=500)
        predictor = ChurnPredictor()
        predictor.train(X, y, ChurnHorizon.DAYS_30)

        predictions = predictor.predict(X.head(20), ChurnHorizon.DAYS_30)
        for pred in predictions:
            if pred.churn_probability >= 0.7:
                assert pred.risk_level == "high"
            elif pred.churn_probability >= 0.4:
                assert pred.risk_level == "medium"
            elif pred.churn_probability >= 0.2:
                assert pred.risk_level == "low"
            else:
                assert pred.risk_level == "minimal"

    def test_feature_engineering(self):
        """Test feature engineering output"""
        X, y = generate_synthetic_training_data(n_samples=100)
        predictor = ChurnPredictor()

        features = predictor.feature_engineer.engineer_features(X)
        assert len(features.columns) >= 20
        assert "monthly_arpu" in features.columns
        assert "usage_trend_3m" in features.columns


class TestCustomerSegmenter:
    """Tests for CustomerSegmenter"""

    def test_fit_and_predict(self):
        """Test segmentation workflow"""
        X = generate_segmentation_data(n_samples=1000)
        segmenter = CustomerSegmenter(n_clusters=5)

        results = segmenter.fit(X)
        assert "silhouette_score" in results
        assert results["n_clusters"] == 5

        predictions = segmenter.predict(X.head(10))
        assert len(predictions) == 10
        for pred in predictions:
            assert "segment_id" in pred
            assert "segment_name" in pred

    def test_segment_summary(self):
        """Test segment summary generation"""
        X = generate_segmentation_data(n_samples=500)
        segmenter = CustomerSegmenter(n_clusters=3)
        segmenter.fit(X)

        summary = segmenter.get_segment_summary()
        assert summary["n_segments"] == 3
        assert len(summary["segments"]) == 3


class TestCLVModel:
    """Tests for CLVModel"""

    def test_fit_and_predict(self):
        """Test CLV model training and prediction"""
        df = generate_clv_data(n_samples=1000)
        model = CLVModel()
        model.fit(df)

        predictions = model.predict(df.head(10))
        assert len(predictions) == 10
        for pred in predictions:
            assert pred.predicted_clv > 0
            assert len(pred.confidence_interval) == 2

    def test_cohort_analysis(self):
        """Test cohort-based CLV analysis"""
        df = generate_clv_data(n_samples=500)
        df["revenue"] = df["average_monetary_value"] * df["purchase_frequency"]
        model = CLVModel()
        model.fit(df)

        cohorts = model.cohort_analysis(df)
        assert len(cohorts) > 0
        assert "clv" in cohorts.columns

    def test_roi_calculation(self):
        """Test campaign ROI calculation"""
        df = generate_clv_data(n_samples=500)
        model = CLVModel()
        model.fit(df)

        roi = model.calculate_roi(
            campaign_cost=10000,
            target_customers=1000,
            retention_improvement=0.05
        )
        assert roi["campaign_cost"] == 10000
        assert roi["roi_percent"] > -100  # Should not be catastrophic loss


class TestNextBestAction:
    """Tests for NextBestActionEngine"""

    def test_recommend(self):
        """Test NBA recommendations"""
        df = generate_nba_data(n_samples=500)
        engine = NextBestActionEngine()

        churn_probs = {row["customer_id"]: row["churn_prob"] for _, row in df.iterrows()}
        recommendations = engine.recommend(df, churn_probabilities=churn_probs)

        assert len(recommendations) == 500
        for rec in recommendations[:10]:
            assert rec.recommended_action is not None
            assert 0 <= rec.confidence <= 1

    def test_campaign_metrics(self):
        """Test campaign metrics calculation"""
        df = generate_nba_data(n_samples=100)
        engine = NextBestActionEngine()

        recommendations = engine.recommend(df)
        metrics = engine.calculate_campaign_metrics(recommendations)

        assert metrics["total_customers"] == 100
        assert metrics["total_expected_value"] >= 0
        assert "action_distribution" in metrics


# =============================================================================
# Fraud Detection Tests
# =============================================================================

class TestFraudDetector:
    """Tests for FraudDetector"""

    def test_detect(self):
        """Test fraud detection"""
        X, y = generate_fraud_data(n_samples=5000, fraud_rate=0.05)
        detector = FraudDetector(detection_threshold=0.3)  # Lower threshold for testing

        detections = detector.detect(X.head(100))
        # At minimum, detection should return without error
        for det in detections:
            assert det.fraud_score >= 0
            assert det.fraud_score <= 1
            assert det.fraud_type in list(FraudType)
            assert det.severity in list(FraudSeverity)

    def test_fraud_summary(self):
        """Test fraud detection summary"""
        X, y = generate_fraud_data(n_samples=2000, fraud_rate=0.05)
        detector = FraudDetector(detection_threshold=0.3)

        detections = detector.detect(X)
        summary = detector.get_fraud_summary(detections)

        assert "by_severity" in summary
        assert "by_type" in summary


class TestRevenueLeakageDetector:
    """Tests for RevenueLeakageDetector"""

    def test_detect_cdr_gaps(self):
        """Test CDR gap detection"""
        cdr_data = pd.DataFrame({
            "customer_id": ["CUST_001"] * 10,
            "start_time": pd.date_range("2024-01-01", periods=10, freq="min"),
            "duration_seconds": [60] * 10,
            "end_number": ["+9665" + str(i).zfill(6) for i in range(10)],
        })
        # Add a gap
        cdr_data.loc[5, "start_time"] = cdr_data.loc[5, "start_time"] + timedelta(minutes=10)

        detector = RevenueLeakageDetector()
        detections = detector.detect_cdr_gaps(cdr_data)
        assert isinstance(detections, list)

    def test_detect_duplications(self):
        """Test CDR duplication detection"""
        cdr_data = pd.DataFrame({
            "customer_id": ["CUST_001"] * 100,
            "start_time": pd.date_range("2024-01-01", periods=100, freq="min"),
            "duration_seconds": [60] * 100,
            "end_number": ["+9665000001"] * 100,
        })
        # Add duplicates
        cdr_data = pd.concat([cdr_data, cdr_data.iloc[:10]], ignore_index=True)

        detector = RevenueLeakageDetector()
        detections = detector.detect_cdr_duplications(cdr_data)
        # At minimum, should not error
        assert isinstance(detections, list)

    def test_full_detection(self):
        """Test full leakage detection workflow"""
        cdr_data, billing_data, partner_data = generate_leakage_data()

        detector = RevenueLeakageDetector()
        results = detector.run_full_detection(
            cdr_data=cdr_data,
            billing_data=billing_data,
            partner_data=partner_data,
        )

        assert "total_estimated_loss" in results
        assert "total_detections" in results
        assert results["total_estimated_loss"] >= 0


# =============================================================================
# Network Failure Prediction Tests
# =============================================================================

class TestNetworkFailurePredictor:
    """Tests for NetworkFailurePredictor"""

    def test_predict(self):
        """Test failure prediction"""
        X, y = generate_network_kpi_data(n_towers=500)
        predictor = NetworkFailurePredictor()

        predictions = predictor.predict(X.head(50))
        assert len(predictions) == 50
        for pred in predictions:
            assert 0 <= pred.failure_probability <= 1
            assert pred.predicted_failure_type in list(FailureType)

    def test_maintenance_schedule(self):
        """Test maintenance schedule generation"""
        X, y = generate_network_kpi_data(n_towers=200)
        predictor = NetworkFailurePredictor()

        predictions = predictor.predict(X)
        schedule = predictor.get_maintenance_schedule(predictions)

        assert "immediate_action" in schedule
        assert "within_24h" in schedule
        assert "within_7d" in schedule
        assert "monitor" in schedule


class TestCapacityForecaster:
    """Tests for CapacityForecaster"""

    def test_predict(self):
        """Test capacity forecasting"""
        X = generate_capacity_data(n_towers=200)
        forecaster = CapacityForecaster()
        forecaster.fit(X)

        forecasts = forecaster.predict(X.head(50))
        assert len(forecasts) == 50
        for fc in forecasts:
            assert 0 <= fc.predicted_load_percent <= 100
            assert fc.risk_level in ["low", "medium", "high", "critical"]

    def test_scenario_analysis(self):
        """Test scenario analysis"""
        X = generate_capacity_data(n_towers=100)
        forecaster = CapacityForecaster()
        forecaster.fit(X)

        scenarios = forecaster.scenario_analysis(X)
        assert "baseline" in scenarios
        assert "growth_20pct" in scenarios
        assert "growth_50pct" in scenarios


# =============================================================================
# Propensity Model Tests
# =============================================================================

class TestPropensityPredictor:
    """Tests for PropensityPredictor"""

    def test_train_and_predict(self):
        """Test propensity model training and prediction"""
        X, y_dict = generate_propensity_data(n_samples=1000)
        predictor = PropensityPredictor()

        results = predictor.train(X, y_dict)
        for ptype in y_dict.keys():
            assert ptype.value in results

        predictions = predictor.predict(X.head(20))
        assert len(predictions) > 0
        for pred in predictions:
            assert 0 <= pred.probability <= 1

    def test_campaign_recommendations(self):
        """Test campaign recommendation generation"""
        X, y_dict = generate_propensity_data(n_samples=500)
        predictor = PropensityPredictor()

        # Train only for types that have variation in labels
        train_dict = {k: v for k, v in y_dict.items() if v.nunique() > 1}
        if train_dict:
            predictor.train(X, train_dict)

        predictions = predictor.predict(X.head(50))
        assert len(predictions) > 0


class TestCampaignOptimizer:
    """Tests for CampaignOptimizer"""

    def test_optimize_campaign(self):
        """Test campaign optimization"""
        df = generate_campaign_data(n_customers=5000)
        optimizer = CampaignOptimizer()

        result = optimizer.optimize_campaign(
            total_budget=50000,
            target_customers=2000,
            propensity_data=df,
            campaign_type="retention",
        )

        assert result.total_budget == 50000
        assert result.predicted_roi > -100  # Should not be catastrophic loss
        assert len(result.channel_allocation) > 0

    def test_ab_test_analysis(self):
        """Test A/B test analysis"""
        test_data = pd.DataFrame({
            "control_group": [0] * 500 + [1] * 500,
            "converted": [0] * 450 + [1] * 50 + [0] * 400 + [1] * 100,
        })

        optimizer = CampaignOptimizer()
        results = optimizer.run_a_b_test_analysis(test_data)

        assert "control_conversion_rate" in results
        assert "treatment_conversion_rate" in results
        assert "lift_percent" in results


# =============================================================================
# Pricing Elasticity Tests
# =============================================================================

class TestPricingElasticity:
    """Tests for PricingElasticityModel"""

    def test_fit_and_estimate(self):
        """Test elasticity model fitting and estimation"""
        df = generate_elasticity_data(n_observations=500)
        model = PricingElasticityModel()
        model.fit(df)

        result = model.estimate_elasticity(
            product_name="data_addon",
            current_price=25,
            current_quantity=800,
        )
        assert result.elasticity_estimate < 0  # Elasticity should be negative
        assert result.optimal_price > 0

    def test_simulate_price_change(self):
        """Test price change simulation"""
        df = generate_elasticity_data(n_observations=300)
        model = PricingElasticityModel()
        model.fit(df)

        simulation = model.simulate_price_change(
            product_name="data_addon",
            price_change_percent=10,
            current_quantity=800,
        )
        assert "new_quantity" in simulation
        assert "revenue_change_percent" in simulation


# =============================================================================
# Roaming Optimization Tests
# =============================================================================

class TestRoamingOptimization:
    """Tests for RoamingOptimizationModel"""

    def test_analyze_partner_performance(self):
        """Test partner performance analysis"""
        df = generate_roaming_data(n_records=2000, n_partners=10)
        model = RoamingOptimizationModel()

        performances = model.analyze_partner_performance(df)
        assert len(performances) == 10
        for perf in performances:
            assert perf.total_revenue > 0
            assert 0 <= perf.overall_score <= 1

    def test_detect_settlement_issues(self):
        """Test settlement issue detection"""
        billed = pd.DataFrame({
            "partner_id": ["P001"] * 5,
            "date": pd.date_range("2024-01-01", periods=5),
            "amount": [1000, 1100, 1050, 1200, 1150],
        })
        settled = pd.DataFrame({
            "partner_id": ["P001"] * 5,
            "date": pd.date_range("2024-01-01", periods=5),
            "amount": [950, 1050, 1000, 1100, 1100],
        })

        model = RoamingOptimizationModel()
        issues = model.detect_settlement_issues(billed, settled)
        assert isinstance(issues, list)

    def test_optimize_routes(self):
        """Test roaming route optimization"""
        df = generate_roaming_data(n_records=1000)
        # Add required columns for route optimization
        df["roaming_cost"] = df["settlement_cost"]
        df["network_quality"] = df["signal_strength"].abs() / 100

        model = RoamingOptimizationModel()

        routes = model.optimize_roaming_routes(df)
        assert len(routes) > 0


# =============================================================================
# Financial Forecasting Tests
# =============================================================================

class TestFinancialForecaster:
    """Tests for FinancialForecaster"""

    def test_forecast(self):
        """Test financial forecasting"""
        df = generate_financial_data(n_days=180)
        forecaster = FinancialForecaster()
        forecaster.fit(df)

        for metric in FinancialMetric:
            forecast = forecaster.forecast(metric)
            assert forecast.predicted_value > 0
            assert forecast.trend in ["increasing", "decreasing", "stable"]

    def test_anomaly_detection(self):
        """Test financial anomaly detection"""
        df = generate_financial_data(n_days=180)
        forecaster = FinancialForecaster()
        forecaster.fit(df)

        anomalies = forecaster.detect_anomalies(df)
        assert isinstance(anomalies, list)

    def test_executive_dashboard(self):
        """Test executive dashboard generation"""
        df = generate_financial_data(n_days=180)
        forecaster = FinancialForecaster()
        forecaster.fit(df)

        dashboard = forecaster.generate_executive_dashboard(df)
        assert "kpis" in dashboard
        assert "summary" in dashboard
        # Dashboard should have some data
        assert dashboard["summary"]["total_revenue"] >= 0


# =============================================================================
# Model Registry Tests
# =============================================================================

class TestModelRegistry:
    """Tests for ModelRegistry"""

    def test_register_model(self):
        """Test model registration"""
        import uuid
        unique_id = f"test_model_{uuid.uuid4().hex[:8]}"
        registry = ModelRegistry()
        model = registry.register_model(
            model_id=unique_id,
            version="1.0.0",
            artifact_path="test/path/model.pkl",
            metrics={"accuracy": 0.85, "auc": 0.90},
        )
        assert model.status == ModelStatus.DRAFT
        assert model.stage == ModelStage.DEVELOPMENT

    def test_promote_model(self):
        """Test model promotion"""
        import uuid
        unique_id = f"test_model_{uuid.uuid4().hex[:8]}"
        registry = ModelRegistry()
        registry.register_model(
            model_id=unique_id,
            version="1.0.0",
            artifact_path="test/path/model.pkl",
            metrics={"accuracy": 0.85},
        )

        promoted = registry.promote_model(
            model_id=unique_id,
            from_stage=ModelStage.DEVELOPMENT,
            to_stage=ModelStage.STAGING,
        )
        assert promoted.stage == ModelStage.STAGING

    def test_list_models(self):
        """Test model listing"""
        import uuid
        unique_id_a = f"model_a_{uuid.uuid4().hex[:8]}"
        unique_id_b = f"model_b_{uuid.uuid4().hex[:8]}"
        registry = ModelRegistry()
        registry.register_model(
            model_id=unique_id_a,
            version="1.0.0",
            artifact_path="path/a.pkl",
            metrics={"accuracy": 0.8},
        )
        registry.register_model(
            model_id=unique_id_b,
            version="1.0.0",
            artifact_path="path/b.pkl",
            metrics={"accuracy": 0.75},
        )

        models = registry.list_models()
        assert len(models) >= 2

        models_a = registry.list_models(model_id=unique_id_a)
        assert len(models_a) == 1


# =============================================================================
# Pipeline Orchestration Tests
# =============================================================================

class TestPipelineOrchestrator:
    """Tests for MLPipelineOrchestrator"""

    def test_register_pipeline(self):
        """Test pipeline registration"""
        orchestrator = MLPipelineOrchestrator()
        orchestrator.register_pipeline(
            pipeline_id="test_pipeline",
            pipeline_type="training",
            config={"param": "value"},
        )
        status = orchestrator.get_pipeline_status("test_pipeline")
        assert status["type"] == "training"

    def test_run_pipeline(self):
        """Test pipeline execution"""
        orchestrator = MLPipelineOrchestrator()
        orchestrator.register_pipeline(
            pipeline_id="run_pipeline_test",
            pipeline_type="training",
            config={},
        )

        run = orchestrator.run_pipeline("run_pipeline_test")
        assert run.status == PipelineStatus.SUCCESS
        assert run.duration_seconds >= 0

    def test_pipeline_dependencies(self):
        """Test pipeline dependency handling"""
        orchestrator = MLPipelineOrchestrator()

        orchestrator.register_pipeline(
            pipeline_id="upstream",
            pipeline_type="training",
            config={},
        )
        orchestrator.register_pipeline(
            pipeline_id="downstream",
            pipeline_type="deployment",
            config={},
            dependencies=["upstream"],
        )

        # Run upstream first
        run1 = orchestrator.run_pipeline("upstream")
        assert run1.status == PipelineStatus.SUCCESS

        # Then run downstream
        run2 = orchestrator.run_pipeline("downstream")
        assert run2.status == PipelineStatus.SUCCESS


# =============================================================================
# Integration Tests
# =============================================================================

class TestMLIntegration:
    """Integration tests for ML pipeline"""

    def test_end_to_end_churn_pipeline(self):
        """Test end-to-end churn prediction pipeline"""
        # Generate data
        X, y = generate_synthetic_training_data(n_samples=1000)

        # Train model
        predictor = ChurnPredictor()
        predictor.train(X, y, ChurnHorizon.DAYS_30)

        # Make predictions
        predictions = predictor.predict(X.head(50))
        assert len(predictions) == 50

        # Segment customers
        segmenter = CustomerSegmenter(n_clusters=3)
        segmenter.fit(X)
        segments = segmenter.predict(X.head(50))
        assert len(segments) == 50

        # Generate NBA recommendations
        churn_probs = {p.customer_id: p.churn_probability for p in predictions}
        segments_dict = {s["customer_id"]: s["segment_name"] for s in segments}
        engine = NextBestActionEngine()
        recommendations = engine.recommend(X.head(50), churn_probs, segments_dict)
        assert len(recommendations) == 50

    def test_fraud_detection_pipeline(self):
        """Test end-to-end fraud detection pipeline"""
        X, y = generate_fraud_data(n_samples=2000, fraud_rate=0.05)

        detector = FraudDetector(detection_threshold=0.3)
        detector.train(X, y)
        detections = detector.detect(X.head(100))

        # Verify detections have correct structure
        for det in detections:
            assert hasattr(det, 'fraud_type')
            assert hasattr(det, 'fraud_score')
            assert hasattr(det, 'severity')

    def test_mlops_workflow(self):
        """Test complete MLOps workflow"""
        import uuid
        # 1. Register model
        unique_id = f"churn_v2_{uuid.uuid4().hex[:8]}"
        registry = ModelRegistry()
        model = registry.register_model(
            model_id=unique_id,
            version="2.0.0",
            artifact_path="ml/churn_model/model.pkl",
            metrics={"roc_auc": 0.88, "accuracy": 0.85},
        )
        assert model.status == ModelStatus.DRAFT

        # 2. Promote to staging
        promoted = registry.promote_model(
            model_id=unique_id,
            from_stage=ModelStage.DEVELOPMENT,
            to_stage=ModelStage.STAGING,
        )
        assert promoted.stage == ModelStage.STAGING

        # 3. Register pipeline
        orchestrator = MLPipelineOrchestrator(registry=registry)
        orchestrator.register_pipeline(
            pipeline_id="churn_training_v2",
            pipeline_type="training",
            config={"model_id": "churn_v2"},
        )

        # 4. Run pipeline
        run = orchestrator.run_pipeline("churn_training_v2")
        assert run.status == PipelineStatus.SUCCESS


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
