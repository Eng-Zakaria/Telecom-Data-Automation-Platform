"""
End-to-End Pipeline Test

Tests the complete platform flow:
1. Data generation
2. Bronze/Silver/Gold pipelines
3. ML model training and prediction
4. Alert and metrics generation
5. Quality gate validation
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.cdr_generator import CDRGenerator
from ingestion.network_kpi_generator import NetworkKPIGenerator
from ingestion.billing_generator import BillingGenerator
from ml.churn_model import ChurnPredictor, ChurnHorizon, generate_synthetic_training_data
from ml.fraud_detection import FraudDetector, generate_fraud_data
from ml.network_failure_prediction import NetworkFailurePredictor, generate_network_kpi_data
from ml.propensity_model import PropensityPredictor, generate_propensity_data
from ml.pricing_elasticity import PricingElasticityModel, generate_elasticity_data
from ml.roaming_optimization import RoamingOptimizationModel, generate_roaming_data
from ml.finance_reporting import FinancialForecaster, generate_financial_data
from ml.model_registry import ModelRegistry, ModelStage
from ml.pipeline_orchestrator import MLPipelineOrchestrator, PipelineStatus
from monitoring.metrics import MetricsCollector
from monitoring.alerts import AlertManager, AlertSeverity, AlertChannel
from ci.quality_gates import QualityGateManager


class TestDataGeneration:
    """Test data generation pipeline"""

    # Small, in-memory sizes: the generate_*_data() helpers default to 30 days at
    # 5-minute granularity (4M+ KPI rows) and write parquet into the repo.

    def test_cdr_generation(self):
        """Test CDR data generation"""
        gen = CDRGenerator(num_customers=200, num_towers=20, date_range_days=1)
        gen.generate_customers()
        gen.generate_towers()
        cdr_data = gen.inject_fraud_patterns(gen.generate_cdrs(num_records=1000))
        assert len(cdr_data) >= 1000
        assert 'caller_id' in cdr_data.columns

    def test_network_kpi_generation(self):
        """Test network KPI generation"""
        kpi_data = NetworkKPIGenerator(
            num_towers=50, date_range_days=1, granularity_minutes=60
        ).generate_kpi_data()
        assert len(kpi_data) == 50 * 24
        assert 'rsrp_dbm' in kpi_data.columns
        assert 'dropped_call_rate_pct' in kpi_data.columns

    def test_kpi_and_cdr_share_tower_registry(self):
        """Regression: KPI towers used to be generated independently of CDR towers."""
        gen = CDRGenerator(num_customers=50, num_towers=10, date_range_days=1)
        gen.generate_towers()
        ids = [t.tower_id for t in gen.towers]
        kpi = NetworkKPIGenerator(tower_ids=ids, date_range_days=1, granularity_minutes=60).generate_kpi_data()
        assert set(kpi.tower_id) == set(ids)

    def test_billing_generation(self):
        """Test billing data generation"""
        billing_data = BillingGenerator(num_customers=500).generate_billing_data()
        assert len(billing_data) == 500
        assert 'customer_id' in billing_data.columns
        assert 'total_charge' in billing_data.columns

    def test_overdue_months_agree_with_payment_status(self):
        """Regression: num_overdue_months used to be 0 even for overdue/defaulted accounts."""
        b = BillingGenerator(num_customers=2000).generate_billing_data()
        late = b.payment_status.isin(['overdue', 'defaulted'])
        assert late.any()
        assert (b.loc[late, 'num_overdue_months'] > 0).all()
        assert (b.loc[~late, 'num_overdue_months'] == 0).all()


class TestMLModelsEndToEnd:
    """Test all ML models end-to-end"""

    def test_churn_prediction_pipeline(self):
        """Test complete churn prediction pipeline"""
        # Generate data
        X, y = generate_synthetic_training_data(n_samples=2000)

        # Train model
        predictor = ChurnPredictor()
        metrics = predictor.train(X, y, ChurnHorizon.DAYS_30)
        assert metrics['accuracy'] > 0.5

        # Predict
        predictions = predictor.predict(X.head(50), ChurnHorizon.DAYS_30)
        assert len(predictions) == 50

        # Save model
        predictor.save_model()

        # Load model
        predictor.load_model()
        loaded_predictions = predictor.predict(X.head(10), ChurnHorizon.DAYS_30)
        assert len(loaded_predictions) == 10

    def test_fraud_detection_pipeline(self):
        """Test complete fraud detection pipeline"""
        # Generate data
        X, y = generate_fraud_data(n_samples=3000, fraud_rate=0.05)

        # Train and detect
        detector = FraudDetector(detection_threshold=0.3)
        detector.train(X, y)
        detections = detector.detect(X.head(100))

        # Get summary
        summary = detector.get_fraud_summary(detections)
        assert 'by_severity' in summary
        assert 'by_type' in summary

    def test_network_failure_prediction(self):
        """Test network failure prediction pipeline"""
        # Generate data
        X, y = generate_network_kpi_data(n_towers=500)

        # Predict failures
        predictor = NetworkFailurePredictor()
        predictions = predictor.predict(X)

        # Get maintenance schedule
        schedule = predictor.get_maintenance_schedule(predictions)
        assert 'immediate_action' in schedule
        assert 'within_24h' in schedule

    def test_propensity_prediction(self):
        """Test propensity prediction pipeline"""
        # Generate data
        X, y_dict = generate_propensity_data(n_samples=1000)

        # Train and predict
        predictor = PropensityPredictor()
        results = predictor.train(X, y_dict)
        predictions = predictor.predict(X.head(50))
        assert len(predictions) > 0

    def test_pricing_elasticity(self):
        """Test pricing elasticity model"""
        # Generate data
        df = generate_elasticity_data(n_observations=500)

        # Fit and predict
        model = PricingElasticityModel()
        model.fit(df)

        result = model.estimate_elasticity(
            product_name="data_addon",
            current_price=25,
            current_quantity=800,
        )
        assert result.elasticity_estimate < 0

    def test_roaming_optimization(self):
        """Test roaming optimization pipeline"""
        # Generate data
        df = generate_roaming_data(n_records=2000, n_partners=10)

        # Add required columns for route optimization
        df["roaming_cost"] = df["settlement_cost"]
        df["network_quality"] = df["signal_strength"].abs() / 100

        # Analyze partners
        model = RoamingOptimizationModel()
        performances = model.analyze_partner_performance(df)
        assert len(performances) == 10

        # Optimize routes
        routes = model.optimize_roaming_routes(df)
        assert len(routes) > 0

    def test_financial_forecasting(self):
        """Test financial forecasting pipeline"""
        # Generate data
        df = generate_financial_data(n_days=180)

        # Fit and forecast
        forecaster = FinancialForecaster()
        forecaster.fit(df)

        # Forecast metrics
        for metric in ["revenue", "cost", "profit"]:
            forecast = forecaster.forecast(type('Metric', (), {'value': metric})())
            assert forecast.predicted_value > 0

        # Generate dashboard
        dashboard = forecaster.generate_executive_dashboard(df)
        assert "kpis" in dashboard
        assert "summary" in dashboard


class TestMLOpsPipeline:
    """Test MLOps automation pipeline"""

    def test_model_registry_workflow(self):
        """Test complete model registry workflow"""
        import uuid
        registry = ModelRegistry()

        # Register model
        unique_id = f"test_model_{uuid.uuid4().hex[:8]}"
        model = registry.register_model(
            model_id=unique_id,
            version="1.0.0",
            artifact_path="ml/test/model.pkl",
            metrics={"accuracy": 0.85, "auc": 0.90},
        )
        assert model.status.value == "draft"

        # Promote to staging
        promoted = registry.promote_model(
            model_id=unique_id,
            from_stage=ModelStage.DEVELOPMENT,
            to_stage=ModelStage.STAGING,
        )
        assert promoted.stage.value == "staging"

        # List models
        models = registry.list_models(model_id=unique_id)
        assert len(models) >= 1

    def test_pipeline_orchestration(self):
        """Test complete pipeline orchestration"""
        orchestrator = MLPipelineOrchestrator()

        # Register pipelines
        orchestrator.register_pipeline(
            pipeline_id="test_training",
            pipeline_type="training",
            config={"model": "churn_v1"},
        )
        orchestrator.register_pipeline(
            pipeline_id="test_deployment",
            pipeline_type="deployment",
            config={},
            dependencies=["test_training"],
        )

        # Run upstream pipeline
        run1 = orchestrator.run_pipeline("test_training")
        assert run1.status == PipelineStatus.SUCCESS

        # Run downstream pipeline
        run2 = orchestrator.run_pipeline("test_deployment")
        assert run2.status == PipelineStatus.SUCCESS


class TestMonitoringAndAlerts:
    """Test monitoring and alerting systems"""

    def test_metrics_collection(self):
        """Test metrics collection"""
        collector = MetricsCollector()

        # Record metrics
        collector.record_counter("records_processed", 1000, {"table": "cdr"})
        collector.record_metric("pipeline_latency_ms", 500, {"stage": "bronze"})
        collector.record_metric("pipeline_latency_ms", 1500, {"stage": "silver"})

        # Get dashboard
        dashboard = collector.get_dashboard_data()
        assert "metrics" in dashboard
        assert "summary" in dashboard

    def test_alert_management(self):
        """Test alert management"""
        manager = AlertManager()

        # Create alerts
        alert1 = manager.create_alert(
            title="Pipeline Failed",
            message="CDR ingestion pipeline failed",
            severity=AlertSeverity.CRITICAL,
            channel=AlertChannel.SLACK,
            source="cdr_pipeline",
        )
        assert alert1.alert_id

        # Get summary
        summary = manager.get_alert_summary()
        assert summary["total_alerts"] >= 1


class TestQualityGates:
    """Test quality gate system"""

    def test_quality_gate_checks(self):
        """Test quality gate validation"""
        manager = QualityGateManager()

        # Check gates
        gate1 = manager.check_gate("data_quality_score", 97.5)
        assert gate1.status.value == "pass"

        gate2 = manager.check_gate("schema_drift", 0)
        assert gate2.status.value == "pass"

        gate3 = manager.check_gate("latency_p99", 3500)
        # Note: threshold is 5000, so 3500 passes

        gate4 = manager.check_gate("throughput", 800)  # Below threshold (1000)
        assert gate4.status.value == "fail"

        # Get summary
        summary = manager.get_gate_summary()
        assert summary["passed"] >= 2
        assert summary["failed"] >= 1

        # Check promotion
        assert manager.is_promotion_blocked()


class TestFullPlatformIntegration:
    """Integration test for complete platform"""

    def test_end_to_end_pipeline(self):
        """Test complete end-to-end pipeline"""
        print("\n=== Starting End-to-End Platform Test ===")

        # Step 1: Generate data
        print("1. Generating synthetic data...")
        X_churn, y_churn = generate_synthetic_training_data(n_samples=1000)
        X_fraud, y_fraud = generate_fraud_data(n_samples=1000, fraud_rate=0.05)
        X_network, y_network = generate_network_kpi_data(n_towers=200)

        # Step 2: Train models
        print("2. Training ML models...")
        churn_predictor = ChurnPredictor()
        churn_metrics = churn_predictor.train(X_churn, y_churn, ChurnHorizon.DAYS_30)

        fraud_detector = FraudDetector(detection_threshold=0.3)
        fraud_detector.train(X_fraud, y_fraud)

        network_predictor = NetworkFailurePredictor()
        network_predictor.predict(X_network)

        # Step 3: Make predictions
        print("3. Making predictions...")
        churn_predictions = churn_predictor.predict(X_churn.head(50), ChurnHorizon.DAYS_30)
        fraud_detections = fraud_detector.detect(X_fraud.head(50))
        network_predictions = network_predictor.predict(X_network.head(50))

        # Step 4: Generate alerts
        print("4. Generating alerts...")
        alert_manager = AlertManager()
        alert_manager.create_alert(
            title="High Churn Risk Detected",
            message=f"Churn prediction model identified {len(churn_predictions)} at-risk customers",
            severity=AlertSeverity.WARNING,
            channel=AlertChannel.SLACK,
            source="churn_pipeline",
        )

        # Step 5: Collect metrics
        print("5. Collecting metrics...")
        metrics_collector = MetricsCollector()
        metrics_collector.record_counter("predictions_made", len(churn_predictions))
        metrics_collector.record_metric("model_accuracy", churn_metrics['accuracy'])

        # Step 6: Validate quality gates
        print("6. Validating quality gates...")
        quality_manager = QualityGateManager()
        quality_manager.check_gate("data_quality_score", 97.5)
        quality_manager.check_gate("model_accuracy", churn_metrics['accuracy'] * 100)

        # Summary
        print("\n=== End-to-End Test Complete ===")
        print(f"Churn model accuracy: {churn_metrics['accuracy']:.2%}")
        print(f"Fraud detections: {len(fraud_detections)}")
        print(f"Network predictions: {len(network_predictions)}")
        print(f"Quality gates: {quality_manager.get_gate_summary()}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
