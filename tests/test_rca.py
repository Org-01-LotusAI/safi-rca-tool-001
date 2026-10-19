#!/usr/bin/env python3
"""
Pytest Acceptance Test Suite for SAFI RCA Engine.

Tests the core invariants: read-only guarantee, SHA enforcement, and output schema compliance.
All external LLM calls are mocked for reliable offline/CI execution.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure we can import rca_engine from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from rca_engine import (
    run_rca_analysis,
    verify_and_prep_git,
    generate_repomap,
    get_repo_file,
    DEFAULT_CONFIG,
)


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def mock_failing_repo(tmp_path):
    """
    Create a fresh Git repository with a known bug for testing.

    Returns:
        tuple: (repo_path: str, exact_sha: str)
    """
    repo_path = tmp_path / "mock_repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path, check=True, capture_output=True
    )

    # Create README.md
    readme_content = "# Payment Core Service\n"
    (repo_path / "README.md").write_text(readme_content)

    # Create AGENTS.md
    agents_content = "# Architecture\nValidators must guard null lookups before property access.\n"
    (repo_path / "AGENTS.md").write_text(agents_content)

    # Create src/validator.py with deliberate bug
    src_dir = repo_path / "src"
    src_dir.mkdir()
    validator_content = '''def validate_transaction(user_record):
    # Deliberate root cause bug: unhandled null customer record dereference
    return user_record.get("balance") > 0
'''
    (src_dir / "validator.py").write_text(validator_content)

    # Commit all files
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit with validator bug"],
        cwd=repo_path, check=True, capture_output=True
    )

    # Get exact SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, check=True, capture_output=True, text=True
    )
    exact_sha = result.stdout.strip()

    return str(repo_path), exact_sha


@pytest.fixture
def sample_evidence():
    """Sample failure evidence for testing."""
    return """Traceback (most recent call last):
  File "src/main.py", line 42, in process_payment
    if validate_transaction(user):
  File "src/validator.py", line 3, in validate_transaction
    return user_record.get("balance") > 0
AttributeError: 'NoneType' object has no attribute 'get'
"""


@pytest.fixture
def mock_llm_response():
    """Mock LLM response matching the expected RCA schema."""
    return {
        "repo": "",  # Will be filled by run_rca_analysis
        "sha": "",   # Will be filled by run_rca_analysis
        "role": "root-cause-analyzer",
        "root_cause": "Null pointer dereference in validate_transaction when user_record is None",
        "affected_component": "src/validator.py:validate_transaction",
        "evidence": [
            "src/validator.py:3",
            "AttributeError: 'NoneType' object has no attribute 'get'"
        ],
        "confidence": "High",
        "uncertainty": "None",
        "recommended_next_action": "Add null check at start of validate_transaction: if user_record is None: return False"
    }


# =============================================================================
# Mock LLM Client Helper
# =============================================================================

class MockOpenAIClient:
    """Mock OpenAI client that returns a predefined response."""

    def __init__(self, response_data):
        self.response_data = response_data
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock(return_value=self._create_response())

    def _create_response(self):
        """Create a mock response object."""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(self.response_data)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        return mock_response


# =============================================================================
# Test Case 1: Read-Only Invariant
# =============================================================================

def test_read_only_invariant(mock_failing_repo, sample_evidence, mock_llm_response):
    """
    Test that run_rca_analysis maintains read-only guarantee:
    git status --porcelain is clean before AND after the run.
    """
    repo_path, exact_sha = mock_failing_repo

    # Update mock response with correct repo/sha
    mock_llm_response["repo"] = repo_path
    mock_llm_response["sha"] = exact_sha

    # Mock the OpenAI client creation
    with patch("rca_engine.create_openai_client") as mock_create_client:
        mock_client = MockOpenAIClient(mock_llm_response)
        mock_create_client.return_value = mock_client

        # Verify working tree is clean BEFORE analysis
        result_before = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True
        )
        assert result_before.stdout.strip() == "", (
            f"Working tree not clean before analysis: {result_before.stdout}"
        )

        # Run analysis
        result = run_rca_analysis(
            repo_path=repo_path,
            sha=exact_sha,
            evidence=sample_evidence,
            sow_content="",
        )

        # Verify working tree is clean AFTER analysis
        result_after = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path, capture_output=True, text=True
        )
        assert result_after.stdout.strip() == "", (
            f"Working tree modified after analysis: {result_after.stdout}"
        )

        # Additional assertions on result
        assert result is not None
        assert result["sha"] == exact_sha


def test_verify_and_prep_git_read_only(mock_failing_repo):
    """Test verify_and_prep_git enforces clean working tree."""
    repo_path, exact_sha = mock_failing_repo

    # Should succeed on clean repo
    verify_and_prep_git(repo_path, exact_sha)

    # Verify still clean
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path, capture_output=True, text=True
    )
    assert result.stdout.strip() == ""


# =============================================================================
# Test Case 2: Exact SHA Enforcement
# =============================================================================

def test_exact_sha_enforcement_fake_sha(mock_failing_repo, sample_evidence):
    """
    Test that passing a fake/non-existent SHA raises RuntimeError.
    """
    repo_path, _ = mock_failing_repo
    fake_sha = "0000000000000000000000000000000000000000"

    with patch("rca_engine.create_openai_client") as mock_create_client:
        # Even with mocked LLM, verify_and_prep_git should fail first
        mock_client = MockOpenAIClient({})
        mock_create_client.return_value = mock_client

        with pytest.raises(RuntimeError) as exc_info:
            run_rca_analysis(
                repo_path=repo_path,
                sha=fake_sha,
                evidence=sample_evidence,
                sow_content="",
            )

        assert "Failed to checkout SHA" in str(exc_info.value) or "not a valid" in str(exc_info.value)


def test_verify_and_prep_git_fake_sha_raises(mock_failing_repo):
    """Test verify_and_prep_git directly with fake SHA."""
    repo_path, _ = mock_failing_repo
    fake_sha = "0000000000000000000000000000000000000000"

    with pytest.raises(RuntimeError) as exc_info:
        verify_and_prep_git(repo_path, fake_sha)

    assert "Failed to checkout SHA" in str(exc_info.value)


def test_exact_sha_enforcement_dirty_working_tree(mock_failing_repo, sample_evidence):
    """
    Test that a dirty working tree before checkout raises RuntimeError.
    """
    repo_path, exact_sha = mock_failing_repo

    # Make the working tree dirty by modifying a file
    (Path(repo_path) / "README.md").write_text("# Modified\n")

    with patch("rca_engine.create_openai_client") as mock_create_client:
        mock_client = MockOpenAIClient({})
        mock_create_client.return_value = mock_client

        with pytest.raises(RuntimeError) as exc_info:
            run_rca_analysis(
                repo_path=repo_path,
                sha=exact_sha,
                evidence=sample_evidence,
                sow_content="",
            )

        assert "not clean before checkout" in str(exc_info.value)


# =============================================================================
# Test Case 3: Output Schema Compliance
# =============================================================================

REQUIRED_KEYS = [
    "repo",
    "sha",
    "role",
    "root_cause",
    "affected_component",
    "evidence",
    "confidence",
    "uncertainty",
    "recommended_next_action",
]


def test_output_schema(mock_failing_repo, sample_evidence, mock_llm_response):
    """
    Test that run_rca_analysis returns a dict with all required keys
    and that sha matches the fixture's exact SHA.
    """
    repo_path, exact_sha = mock_failing_repo

    # Update mock response
    mock_llm_response["repo"] = repo_path
    mock_llm_response["sha"] = exact_sha

    with patch("rca_engine.create_openai_client") as mock_create_client:
        mock_client = MockOpenAIClient(mock_llm_response)
        mock_create_client.return_value = mock_client

        result = run_rca_analysis(
            repo_path=repo_path,
            sha=exact_sha,
            evidence=sample_evidence,
            sow_content="",
        )

    # Assert all required keys present
    for key in REQUIRED_KEYS:
        assert key in result, f"Missing required key: {key}"

    # Assert sha matches exactly
    assert result["sha"] == exact_sha, f"SHA mismatch: got {result['sha']}, expected {exact_sha}"

    # Assert role is correct
    assert result["role"] == "root-cause-analyzer"

    # Assert confidence is valid
    assert result["confidence"] in ["High", "Medium", "Low"]

    # Assert evidence is a list
    assert isinstance(result["evidence"], list)

    # Assert repo path matches
    assert result["repo"] == repo_path


def test_output_schema_with_partial_llm_response(mock_failing_repo, sample_evidence):
    """
    Test that run_rca_analysis validates and enriches the LLM response
    even if some fields are missing (should raise RuntimeError).
    """
    repo_path, exact_sha = mock_failing_repo

    # Incomplete response missing required fields
    incomplete_response = {
        "root_cause": "Some cause",
        # Missing: repo, sha, role, affected_component, evidence, confidence, uncertainty, recommended_next_action
    }

    with patch("rca_engine.create_openai_client") as mock_create_client:
        mock_client = MockOpenAIClient(incomplete_response)
        mock_create_client.return_value = mock_client

        with pytest.raises(RuntimeError) as exc_info:
            run_rca_analysis(
                repo_path=repo_path,
                sha=exact_sha,
                evidence=sample_evidence,
                sow_content="",
            )

        assert "Missing required field" in str(exc_info.value)


# =============================================================================
# Additional Helper Tests
# =============================================================================

def test_generate_repomap_runs(mock_failing_repo):
    """Test that generate_repomap executes without error."""
    repo_path, _ = mock_failing_repo

    # This may return error message if aider not installed, but shouldn't crash
    result = generate_repomap(repo_path)
    assert isinstance(result, str)


def test_get_repo_file_reads_existing(mock_failing_repo):
    """Test get_repo_file reads existing files."""
    repo_path, _ = mock_failing_repo

    readme = get_repo_file(repo_path, "README.md")
    assert "Payment Core Service" in readme

    agents = get_repo_file(repo_path, "AGENTS.md")
    assert "Validators must guard null lookups" in agents


def test_get_repo_file_missing_returns_empty(mock_failing_repo):
    """Test get_repo_file returns empty string for missing files."""
    repo_path, _ = mock_failing_repo

    result = get_repo_file(repo_path, "NONEXISTENT.md")
    assert result == ""


def test_verify_and_prep_git_not_a_git_repo(tmp_path):
    """Test verify_and_prep_git fails on non-git directory."""
    non_git_dir = tmp_path / "not_a_repo"
    non_git_dir.mkdir()

    with pytest.raises(RuntimeError) as exc_info:
        verify_and_prep_git(str(non_git_dir), "abc123")

    assert "not a valid Git work tree" in str(exc_info.value)


# =============================================================================
# Integration-style Test (Full Pipeline)
# =============================================================================

def test_full_pipeline_integration(mock_failing_repo, sample_evidence, mock_llm_response):
    """
    End-to-end test of the full RCA pipeline with mocked LLM.
    Verifies all components work together correctly.
    """
    repo_path, exact_sha = mock_failing_repo
    mock_llm_response["repo"] = repo_path
    mock_llm_response["sha"] = exact_sha

    with patch("rca_engine.create_openai_client") as mock_create_client:
        mock_client = MockOpenAIClient(mock_llm_response)
        mock_create_client.return_value = mock_client

        result = run_rca_analysis(
            repo_path=repo_path,
            sha=exact_sha,
            evidence=sample_evidence,
            sow_content="Payment service must handle null users gracefully.",
        )

    # Verify complete schema
    for key in REQUIRED_KEYS:
        assert key in result

    # Verify content quality
    assert "validate_transaction" in result["affected_component"]
    assert "null" in result["root_cause"].lower() or "None" in result["root_cause"]
    assert len(result["evidence"]) > 0
    assert result["confidence"] in ["High", "Medium", "Low"]
    assert len(result["recommended_next_action"]) > 10

    # Verify SHA grounding
    assert result["sha"] == exact_sha


# =============================================================================
# Test Configuration
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])