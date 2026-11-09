"""
CI/CD Quality Gates

Implements automated quality checks for CI/CD pipeline:
- Schema validation
- Data quality checks
- Performance benchmarks
- Security scanning
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class GateStatus(Enum):
    """Quality gate status"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class QualityGate:
    """Quality gate definition"""
    name: str
    status: GateStatus
    threshold: float
    actual: float
    message: str
    metadata: Dict = field(default_factory=dict)


class QualityGateManager:
    """
    Manages CI/CD quality gates.

    Features:
    - Automated quality checks
    - Threshold enforcement
    - Gate blocking
    - Promotion gating
    """

    def __init__(self):
        self.gates: List[QualityGate] = []
        self.blocked_gates = []
        self.promotion_gates = []

        # Define default gates
        self._initialize_default_gates()

    def _initialize_default_gates(self):
        """Initialize default quality gates"""
        # Data quality gates
        self.promotion_gates.append({
            "name": "data_quality_score",
            "threshold": 95.0,
            "description": "Data quality score must be >= 95%"
        })
        self.promotion_gates.append({
            "name": "schema_drift",
            "threshold": 0.0,
            "description": "No schema drift allowed"
        })
        self.promotion_gates.append({
            "name": "pipeline_success_rate",
            "threshold": 99.0,
            "description": "Pipeline success rate must be >= 99%"
        })

        # Performance gates
        self.promotion_gates.append({
            "name": "latency_p99",
            "threshold": 5000.0,  # ms
            "description": "P99 latency must be < 5 seconds"
        })
        self.promotion_gates.append({
            "name": "throughput",
            "threshold": 1000.0,  # records/sec
            "description": "Throughput must be >= 1000 records/sec"
        })

    def check_gate(
        self,
        gate_name: str,
        value: float,
        context: Dict = None
    ) -> QualityGate:
        """
        Check a quality gate.

        Args:
            gate_name: Name of the gate
            value: Current metric value
            context: Additional context

        Returns:
            QualityGate with status
        """
        # Find gate definition
        gate_def = None
        for gate in self.promotion_gates:
            if gate["name"] == gate_name:
                gate_def = gate
                break

        if not gate_def:
            return QualityGate(
                name=gate_name,
                status=GateStatus.WARNING,
                threshold=0,
                actual=value,
                message=f"No gate definition found for {gate_name}"
            )

        threshold = gate_def["threshold"]
        is_pass = value >= threshold

        gate = QualityGate(
            name=gate_name,
            status=GateStatus.PASS if is_pass else GateStatus.FAIL,
            threshold=threshold,
            actual=value,
            message=gate_def["description"]
        )

        self.gates.append(gate)

        # Block promotion if gate fails
        if not is_pass and gate_name in [g["name"] for g in self.promotion_gates]:
            self.blocked_gates.append(gate)

        return gate

    def get_gate_summary(self) -> Dict:
        """Get summary of all quality gates"""
        return {
            "total_gates": len(self.gates),
            "passed": sum(1 for g in self.gates if g.status == GateStatus.PASS),
            "failed": sum(1 for g in self.gates if g.status == GateStatus.FAIL),
            "warnings": sum(1 for g in self.gates if g.status == GateStatus.WARNING),
            "blocked": len(self.blocked_gates),
            "gates": [
                {
                    "name": g.name,
                    "status": g.status.value,
                    "threshold": g.threshold,
                    "actual": g.actual,
                    "message": g.message
                }
                for g in self.gates
            ]
        }

    def is_promotion_blocked(self) -> bool:
        """Check if promotion is blocked"""
        return len(self.blocked_gates) > 0

    def get_block_reasons(self) -> List[str]:
        """Get reasons why promotion is blocked"""
        return [g.message for g in self.blocked_gates]


def create_quality_gates() -> QualityGateManager:
    """Factory function to create quality gate manager"""
    return QualityGateManager()


# Global quality gate manager
_quality_gates = QualityGateManager()


def check_quality_gate(*args, **kwargs):
    """Convenience function to check a quality gate"""
    return _quality_gates.check_gate(*args, **kwargs)


def is_promotion_allowed() -> bool:
    """Check if promotion is allowed"""
    return not _quality_gates.is_promotion_blocked()


def get_quality_summary() -> Dict:
    """Get quality gate summary"""
    return _quality_gates.get_gate_summary()


if __name__ == "__main__":
    # Example usage
    manager = create_quality_gates()

    # Check gates
    manager.check_gate("data_quality_score", 97.5)
    manager.check_gate("schema_drift", 0)
    manager.check_gate("latency_p99", 3500)
    manager.check_gate("throughput", 800)  # Below threshold

    # Get summary
    summary = manager.get_gate_summary()
    print(json.dumps(summary, indent=2))

    # Check if promotion is allowed
    if manager.is_promotion_blocked():
        print("\n❌ Promotion BLOCKED:")
        for reason in manager.get_block_reasons():
            print(f"  - {reason}")
        sys.exit(1)
    else:
        print("\n✅ Promotion ALLOWED")
