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
        'ci',
        'docs',
        'docs/decisions',
    ]

    for dir_path in expected_dirs:
        full_path = root / dir_path
        assert full_path.exists(), f"Missing directory: {dir_path}"


ENVIRONMENTS = ['dev', 'staging', 'prod', 'ephemeral']


@pytest.mark.parametrize('env', ENVIRONMENTS)
def test_environment_is_a_thin_root_over_platform(env):
    """Environments must not drift: each one only calls modules/platform with inputs."""
    root = Path(__file__).parent.parent / 'infra' / 'environments' / env
    main = (root / 'main.tf').read_text(encoding='utf-8')
    versions = (root / 'versions.tf').read_text(encoding='utf-8')

    assert main.count('module "') == 1, f"{env} should call exactly one module"
    assert 'source      = "../../modules/platform"' in main
    assert 'resource "' not in main, f"{env} must not declare resources directly"
    assert 'hashicorp/azurerm' in versions and '~> 4.' in versions
    assert 'microsoft/fabric' in versions
    assert 'backend "azurerm"' in versions


def test_terraform_avoids_known_footguns():
    """Regression guard for defects fixed in the module rewrite."""
    modules = Path(__file__).parent.parent / 'infra' / 'modules'
    sources = {p: p.read_text(encoding='utf-8') for p in modules.rglob('*.tf')}

    for path, text in sources.items():
        assert 'timestamp()' not in text, f"{path}: timestamp() in config forces a diff on every plan"
        assert 'enable_https_traffic_only' not in text, f"{path}: removed in azurerm 4.x"
        assert 'azurerm_fabric_workspace' not in text, f"{path}: not an azurerm resource, use microsoft/fabric"

    lake = sources[modules / 'storage' / 'blob' / 'main.tf']
    assert 'is_hns_enabled                  = true' in lake, "lake must be ADLS Gen2"
    assert 'shared_access_key_enabled       = false' in lake, "lake must be Entra ID only"


def test_readme_exists():
    """Verify README exists and has content"""
    readme = Path(__file__).parent.parent / 'README.md'
    assert readme.exists()
    content = readme.read_text(encoding='utf-8')
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
    """Project compose runs only project-specific services; Azure emulators come from azure-local-lab."""
    compose = (Path(__file__).parent.parent / 'docker-compose.yml').read_text(encoding='utf-8')
    assert 'services:' in compose
    assert 'marquez' in compose, "lineage backend"
    assert 'azure-local-lab' in compose, "must point at the shared emulator stack"
    for retired in ('minio', 'redpanda'):  # never used by the code; Event Hubs + Azurite replace them
        assert f'image: {retired}' not in compose and f'{retired}:' not in compose


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
