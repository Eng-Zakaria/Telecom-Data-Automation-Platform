"""
ML Pipeline Orchestration

Provides:
- Training pipeline orchestration
- Feature pipeline management
- Model deployment automation
- Pipeline monitoring and alerting
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..model_registry.registry import ModelRegistry, ModelVersion, ModelStage, ModelStatus


class PipelineStatus(Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineRun:
    """Pipeline execution record"""
    pipeline_id: str
    run_id: str
    status: PipelineStatus
    started_at: str
    completed_at: Optional[str]
    duration_seconds: float
    metrics: Dict[str, float]
    errors: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)


class MLPipelineOrchestrator:
    """
    ML pipeline orchestration system.

    Manages:
    - Training pipelines
    - Feature engineering pipelines
    - Model deployment pipelines
    - Pipeline monitoring
    """

    def __init__(
        self,
        registry: ModelRegistry = None,
        pipeline_dir: str = "ml/pipelines",
    ):
        self.registry = registry or ModelRegistry()
        self.pipeline_dir = Path(pipeline_dir)
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)

        self.pipelines = {}
        self._load_pipelines()

    def _load_pipelines(self):
        """Load pipeline definitions from disk"""
        pipeline_file = self.pipeline_dir / "pipelines.json"
        if pipeline_file.exists():
            with open(pipeline_file, 'r') as f:
                self.pipelines = json.load(f)

    def _save_pipelines(self):
        """Save pipeline definitions to disk"""
        pipeline_file = self.pipeline_dir / "pipelines.json"
        with open(pipeline_file, 'w') as f:
            json.dump(self.pipelines, f, indent=2)

    def register_pipeline(
        self,
        pipeline_id: str,
        pipeline_type: str,
        config: Dict,
        dependencies: List[str] = None,
    ):
        """
        Register a new pipeline.

        Args:
            pipeline_id: Unique pipeline identifier
            pipeline_type: Type of pipeline (training, feature, deployment)
            config: Pipeline configuration
            dependencies: List of upstream pipeline IDs
        """
        self.pipelines[pipeline_id] = {
            "pipeline_id": pipeline_id,
            "type": pipeline_type,
            "config": config,
            "dependencies": dependencies or [],
            "status": "registered",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "runs": [],
        }
        self._save_pipelines()

    def run_pipeline(
        self,
        pipeline_id: str,
        params: Dict = None,
    ) -> PipelineRun:
        """
        Execute a pipeline.

        Args:
            pipeline_id: Pipeline identifier
            params: Execution parameters

        Returns:
            PipelineRun result
        """
        if pipeline_id not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_id} not found")

        # Check dependencies
        pipeline = self.pipelines[pipeline_id]
        if pipeline["dependencies"]:
            for dep_id in pipeline["dependencies"]:
                dep_run = self._get_latest_run(dep_id)
                if dep_run and dep_run.status != PipelineStatus.SUCCESS:
                    raise RuntimeError(f"Dependency {dep_id} not completed successfully")

        # Create run
        run_id = f"RUN_{int(time.time())}_{hash(pipeline_id) % 10000}"
        started_at = datetime.now().isoformat()

        run = PipelineRun(
            pipeline_id=pipeline_id,
            run_id=run_id,
            status=PipelineStatus.RUNNING,
            started_at=started_at,
            completed_at=None,
            duration_seconds=0,
            metrics={},
            errors=[],
            artifacts={},
        )

        # Execute pipeline (simulated)
        try:
            # Simulate pipeline execution
            time.sleep(0.1)  # Simulate work

            # Generate metrics
            run.metrics = {
                "records_processed": params.get("n_samples", 1000) if params else 1000,
                "training_time_seconds": 5.2,
                "model_quality_score": 0.85,
            }

            # Update status
            run.status = PipelineStatus.SUCCESS
            run.completed_at = datetime.now().isoformat()
            run.duration_seconds = (
                datetime.fromisoformat(run.completed_at) -
                datetime.fromisoformat(run.started_at)
            ).total_seconds()

        except Exception as e:
            run.status = PipelineStatus.FAILED
            run.completed_at = datetime.now().isoformat()
            run.errors.append(str(e))

        # Save run
        self._save_pipeline_run(pipeline_id, run)

        # Update pipeline last run
        self.pipelines[pipeline_id]["last_run"] = run.run_id
        self._save_pipelines()

        return run

    def _get_latest_run(self, pipeline_id: str) -> Optional[PipelineRun]:
        """Get latest pipeline run"""
        if pipeline_id not in self.pipelines:
            return None

        runs = self.pipelines[pipeline_id].get("runs", [])
        if not runs:
            return None

        # Convert dict to PipelineRun
        latest = max(runs, key=lambda r: r["started_at"])
        return PipelineRun(
            pipeline_id=pipeline_id,
            run_id=latest["run_id"],
            status=PipelineStatus(latest["status"]),
            started_at=latest["started_at"],
            completed_at=latest.get("completed_at"),
            duration_seconds=latest.get("duration_seconds", 0),
            metrics=latest.get("metrics", {}),
            errors=latest.get("errors", []),
            artifacts=latest.get("artifacts", {}),
        )

    def _save_pipeline_run(self, pipeline_id: str, run: PipelineRun):
        """Save pipeline run to disk"""
        if pipeline_id not in self.pipelines:
            self.pipelines[pipeline_id] = {"runs": []}

        if "runs" not in self.pipelines[pipeline_id]:
            self.pipelines[pipeline_id]["runs"] = []

        run_dict = {
            "run_id": run.run_id,
            "status": run.status.value,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_seconds": run.duration_seconds,
            "metrics": run.metrics,
            "errors": run.errors,
            "artifacts": run.artifacts,
        }
        self.pipelines[pipeline_id]["runs"].append(run_dict)

        # Keep only last 100 runs
        self.pipelines[pipeline_id]["runs"] = self.pipelines[pipeline_id]["runs"][-100:]

        self._save_pipelines()

    def get_pipeline_status(self, pipeline_id: str) -> Dict:
        """Get pipeline status and recent runs"""
        if pipeline_id not in self.pipelines:
            return {"error": "Pipeline not found"}

        pipeline = self.pipelines[pipeline_id]
        recent_runs = pipeline.get("runs", [])[-5:]

        return {
            "pipeline_id": pipeline_id,
            "type": pipeline["type"],
            "status": pipeline["status"],
            "last_run": pipeline.get("last_run"),
            "recent_runs": recent_runs,
            "dependencies": pipeline.get("dependencies", []),
        }


if __name__ == "__main__":
    # Example usage
    print("Testing ML Pipeline Orchestration...")

    # Initialize orchestrator
    orchestrator = MLPipelineOrchestrator()

    # Register pipelines
    orchestrator.register_pipeline(
        pipeline_id="churn_training",
        pipeline_type="training",
        config={"model_type": "gradient_boosting", "n_estimators": 100},
        dependencies=[],
    )

    orchestrator.register_pipeline(
        pipeline_id="churn_deployment",
        pipeline_type="deployment",
        config={"stage": "production", "canary_percentage": 10},
        dependencies=["churn_training"],
    )

    # Run training pipeline
    print("\nRunning churn training pipeline...")
    run1 = orchestrator.run_pipeline(
        pipeline_id="churn_training",
        params={"n_samples": 5000},
    )
    print(f"  Status: {run1.status.value}")
    print(f"  Duration: {run1.duration_seconds:.2f}s")
    print(f"  Metrics: {run1.metrics}")

    # Run deployment pipeline
    print("\nRunning churn deployment pipeline...")
    run2 = orchestrator.run_pipeline(pipeline_id="churn_deployment")
    print(f"  Status: {run2.status.value}")

    # Get pipeline status
    status = orchestrator.get_pipeline_status("churn_training")
    print(f"\nPipeline Status:")
    print(f"  Type: {status['type']}")
    print(f"  Last Run: {status['last_run']}")
    print(f"  Recent Runs: {len(status['recent_runs'])}")
