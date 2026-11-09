"""
ML Model Integration Tests

Tests integration between ML models and the data platform:
- Data generator to model training
- Model output to downstream consumption
- End-to-end pipeline validation
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.cdr_generator import CDRGenerator
from ingestion.network_kpi_generator import NetworkKPIGenerator
from ml.churn_model import ChurnPredictor, ChurnHorizon, CustomerSegmenter, generate_synthetic_training_data
from ml.churn_model import ChurnPredictor, generate_synthetic_training_data
from ml.fraud_detection import FraudDetector, generate_fraud_data
from ml.network_failure_prediction import NetworkFailurePredictor, CapacityForecaster, generate_network_kpi_data
from ml.propensity_model import PropensityPredictor, generate_propensity_data


class TestGeneratorToModelIntegration:
    """Test integration between data generators and ML models"""

    def test_cdr_to_churn_features(self):
        """Test CDR data can be used for churn features"""
        # Generate synthetic churn data
        df, _ = generate_synthetic_training_data(n_samples=100)

        # Verify feature compatibility
        predictor = ChurnPredictor()
        features = predictor.feature_engineer.engineer_features(df)
        assert len(features.columns) >= 20

    def test_network_kpi_to_failure_prediction(self):
        """Test network KPI data for failure prediction"""
        # Prepare for model
        X, y = generate_network_kpi_data(n_towers=200)

        # Train and predict
        predictor = NetworkFailurePredictor()
        predictions = predictor.predict(X.head(50))
        assert len(predictions) == 50

    def test_fraud_data_pipeline(self):
        """Test fraud detection with synthetic data"""
        X, y = generate_fraud_data(n_samples=2000, fraud_rate=0.05)

        detector = FraudDetector()
        detections = detector.detect(X.head(100))

        # Verify detections have correct structure
        for det in detections:
            assert hasattr(det, 'fraud_type')
            assert hasattr(det, 'fraud_score')
            assert hasattr(det, 'severity')


class TestModelOutputConsumption:
    """Test that model outputs can be consumed downstream"""

    def test_churn_predictions_format(self):
        """Test churn predictions are in correct format"""
        X, y = generate_synthetic_training_data(n_samples=500)
        predictor = ChurnPredictor()
        predictor.train(X, y)

        predictions = predictor.predict(X.head(20))
        for pred in predictions:
            assert hasattr(pred, 'customer_id')
            assert hasattr(pred, 'churn_probability')
            assert hasattr(pred, 'risk_level')
            assert hasattr(pred, 'top_features')

    def test_fraud_detections_format(self):
        """Test fraud detections are consumable"""
        X, y = generate_fraud_data(n_samples=1000)
        detector = FraudDetector()
        detections = detector.detect(X)

        for det in detections:
            assert hasattr(det, 'transaction_id')
            assert hasattr(det, 'customer_id')
            assert hasattr(det, 'fraud_type')
            assert hasattr(det, 'recommendation')

    def test_network_predictions_format(self):
        """Test network predictions are consumable"""
        X, y = generate_network_kpi_data(n_towers=200)
        predictor = NetworkFailurePredictor()
        predictions = predictor.predict(X)

        for pred in predictions:
            assert hasattr(pred, 'tower_id')
            assert hasattr(pred, 'failure_probability')
            assert hasattr(pred, 'predicted_failure_type')
            assert hasattr(pred, 'recommended_action')


class TestEndToEndPipeline:
    """End-to-end pipeline validation"""

    def test_full_churn_pipeline(self):
        """Test complete churn prediction pipeline"""
        # Step 1: Generate training data
        X, y = generate_synthetic_training_data(n_samples=2000, churn_rate=0.15)

        # Step 2: Train model
        predictor = ChurnPredictor()
        metrics = predictor.train(X, y, ChurnHorizon.DAYS_30)
        assert metrics["accuracy"] > 0.5

        # Step 3: Make predictions
        predictions = predictor.predict(X.head(100), ChurnHorizon.DAYS_30)

        # Step 4: Segment customers
        segmenter = CustomerSegmenter(n_clusters=3)
        segmenter.fit(X)
        segments = segmenter.predict(X.head(100))

        # Step 5: Generate recommendations
        from ml.churn_model import NextBestActionEngine
        churn_probs = {p.customer_id: p.churn_probability for p in predictions}
        segments_dict = {s["customer_id"]: s["segment_name"] for s in segments}
        engine = NextBestActionEngine()
        recommendations = engine.recommend(X.head(100), churn_probs, segments_dict)

        # Verify outputs
        assert len(predictions) == 100
        assert len(segments) == 100
        assert len(recommendations) == 100

    def test_full_fraud_pipeline(self):
        """Test complete fraud detection pipeline"""
        # Generate data
        X, y = generate_fraud_data(n_samples=5000, fraud_rate=0.05)

        # Train and detect
        detector = FraudDetector(detection_threshold=0.3)
        detector.train(X, y)
        detections = detector.detect(X)

        # Get summary
        summary = detector.get_fraud_summary(detections)

        # Verify
        assert "by_severity" in summary
        assert "by_type" in summary

    def test_full_network_pipeline(self):
        """Test complete network failure prediction pipeline"""
        # Generate data
        X, y = generate_network_kpi_data(n_towers=500)

        # Predict failures
        predictor = NetworkFailurePredictor()
        predictions = predictor.predict(X)

        # Generate maintenance schedule
        schedule = predictor.get_maintenance_schedule(predictions)

        # Forecast capacity
        forecaster = CapacityForecaster()
        forecaster.fit(X)
        forecasts = forecaster.predict(X.head(50))

        # Verify outputs
        assert len(predictions) == 500
        assert len(forecasts) == 50
        assert "immediate_action" in schedule


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
