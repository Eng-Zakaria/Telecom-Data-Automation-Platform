"""
Phase 0 Test Suite
Validates repository structure and basic configuration
"""

import os
import pytest
from pathlib import Path


def test_repository_structure():
    """Verify all Phase 0 directories exist"""
    root = Path(__file__).parent.parent

    expected_dirs = [
        'infra',
        'infra/modules',
        'infra/environments',
        'ingestion',
        'pipelines',
        'transform',
        'ml',
        'quality',
        'automation',
        'ci',
        'docs',
        'docs/decisions',
        'docs/domains',
    ]

    for dir_path in expected_dirs:
        full_path = root / dir_path
        assert full_path.exists(), f"Missing directory: {dir_path}"


def test_terraform_files():
    """Verify Terraform configuration files exist"""
    infra = Path(__file__).parent.parent / 'infra'

    required_files = [
        'main.tf',
        'versions.tf',
        'environments/dev/main.tf',
        'environments/staging/main.tf',
        'environments/prod/main.tf',
        'environments/ephemeral/main.tf',
    ]

    for file_path in required_files:
        full_path = infra / file_path
        assert full_path.exists(), f"Missing Terraform file: {file_path}"


def test_readme_exists():
    """Verify README exists and has content"""
    readme = Path(__file__).parent.parent / 'README.md'
    assert readme.exists()
    content = readme.read_text()
    assert len(content) > 1000, "README should have substantial content"


def test_documentation_files():
    """Verify documentation files exist"""
    docs = Path(__file__).parent.parent / 'docs'

    required_docs = [
        'architecture.md',
        'runbook.md',
    ]

    for doc_file in required_docs:
        full_path = docs / doc_file
        assert full_path.exists(), f"Missing documentation: {doc_file}"


def test_ade_files():
    """Verify ADR files exist"""
    decisions = Path(__file__).parent.parent / 'docs' / 'decisions'

    required_adrs = [
        'ADR-001-local-cloud-parity.md',
        'ADR-002-terraform-vs-fabric-cli.md',
        'ADR-003-ephemeral-environments.md',
        'ADR-004-secrets-management.md',
        'ADR-005-ci-cd-promotion.md',
    ]

    for adr in required_adrs:
        full_path = decisions / adr
        assert full_path.exists(), f"Missing ADR: {adr}"


def test_docker_compose():
    """Verify Docker Compose file exists"""
    dockerfile = Path(__file__).parent.parent / 'docker-compose.yml'
    assert dockerfile.exists()
    content = dockerfile.read_text()
    assert 'services:' in content
    assert 'azurite' in content
    assert 'minio' in content
    assert 'redpanda' in content
    assert 'postgres' in content


def test_env_example():
    """Verify environment template exists"""
    env_file = Path(__file__).parent.parent / '.env.example'
    assert env_file.exists()


def test_github_workflows():
    """Verify GitHub Actions workflows exist"""
    workflows = Path(__file__).parent.parent / '.github' / 'workflows'

    required_workflows = [
        'ci.yml',
        'promote.yml',
        'ephemeral.yml',
    ]

    for workflow in required_workflows:
        full_path = workflows / workflow
        assert full_path.exists(), f"Missing workflow: {workflow}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
