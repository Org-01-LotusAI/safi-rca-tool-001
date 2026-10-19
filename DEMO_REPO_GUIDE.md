# Demo Repository Guide for SAFI RCA Tool

This guide explains how to create a demonstration Git repository for testing the SAFI Root Cause Analyzer (RCA) tool.

## Quick Start: Create Demo Repo

Run this script to create a demo repo ready for RCA analysis:

```bash
python3 -c "
import subprocess
from pathlib import Path
import tempfile
import os

# Create temp directory for demo repo
tmp_dir = Path(tempfile.mkdtemp())
repo_path = tmp_dir / 'demo_repo'
repo_path.mkdir()

# Initialize git repo
subprocess.run(['git', 'init'], cwd=repo_path, check=True, capture_output=True)
subprocess.run(
    ['git', 'config', 'user.name', 'Test User'],
    cwd=repo_path, check=True, capture_output=True
)
subprocess.run(
    ['git', 'config', 'user.email', 'test@example.com'],
    cwd=repo_path, check=True, capture_output=True
)

# Create README.md
readme_content = '# Payment Core Service\n'
(readme_path := repo_path / 'README.md').write_text(readme_content)

# Create AGENTS.md
agents_content = '# Architecture\nValidators must guard null lookups before property access.\n'
(repo_path / 'AGENTS.md').write_text(agents_content)

# Create src/validator.py with deliberate bug
src_dir = repo_path / 'src'
src_dir.mkdir()
validator_content = '''def validate_transaction(user_record):
    # Deliberate root cause bug: unhandled null customer record dereference
    return user_record.get('balance') > 0
'''
(src_dir / 'validator.py').write_text(validator_content)

# Commit all files
subprocess.run(['git', 'add', '.'], cwd=repo_path, check=True, capture_output=True)
subprocess.run(
    ['git', 'commit', '-m', 'Initial commit with validator bug'],
    cwd=repo_path, check=True, capture_output=True
)

# Get exact SHA
result = subprocess.run(
    ['git', 'rev-parse', 'HEAD'],
    cwd=repo_path, check=True, capture_output=True, text=True
)
exact_sha = result.stdout.strip()

print(f'Demo repo created at: {repo_path}')
print(f'Exact SHA: {exact_sha}')
print()
print('Files created:')
for f in sorted(repo_path.rglob('*')):
    if f.is_file():
        print(f'  {f.relative_to(repo_path)}')
"
```

## Demo Repo Structure

A minimal demo repo for SAFI RCA should contain:

```
demo_repo/
├── README.md          # Repository overview
├── AGENTS.md          # Architecture/constraints (required by test fixtures)
├── src/
│   └── validator.py   # Code with the bug being analyzed
└── .agents/
    └── skills/
        └── root-cause-analyzer.md  # Skill definition (optional, copied from source)
```

## Failure Evidence Format

The tool expects failure evidence in `.txt` or `.log` format. Create a sample evidence file:

```
Traceback (most recent call last):
  File "src/main.py", line 42, in process_payment
    if validate_transaction(user):
  File "src/validator.py", line 3, in validate_transaction
    return user_record.get("balance") > 0
AttributeError: 'NoneType' object has no attribute 'get'
```

**Key elements the RCA looks for:**
- Stack trace with file paths and line numbers
- Function call chain
- Specific error type (AttributeError, TypeError, etc.)
- The problematic code pattern (null dereference)

## SOW (Statement of Work) Example

Optional, but adds context:

```markdown
# Statement of Work: Payment Service

## Overview
The payment service must handle user records securely, including null user records.

## Requirements
1. Validate transaction before processing
2. Handle null customer records gracefully
3. Return appropriate error messages for invalid states
4. Maintain audit logs for all transactions
```

## How to Run the RCA Analysis

### Using the CLI

```bash
# 1. Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment variables
export RCA_MODEL_NAME="Nemotron 3 Ultra"
export RCA_API_BASE_URL="https://your-endpoint/v1"
export RCA_API_KEY="sk-..."

# 3. Run CLI analysis
python rca_engine.py analyze \
  --repo /path/to/demo_repo \
  --sha <EXACT_SHA_FROM_DEMO> \
  --evidence ./evidence.txt \
  --sow ./sow.md
```

### Using the Web UI (Streamlit)

```bash
streamlit run app.py
# Then open http://localhost:8501 in your browser
# Enter the demo repo path, SHA, upload evidence file and optionally SOW
```

## Test Suite Integration

The existing tests use a pytest fixture `mock_failing_repo`. To add your demo repo to the test suite:

1. Create the repo using the script above
2. Use the fixture in your tests:

```python
@pytest.fixture
def my_demo_repo(tmp_path):
    """Create a demo repo for testing."""
    # Copy or replicate the demo repo structure
    repo_path = tmp_path / "my_demo"
    repo_path.mkdir()
    # ... set up files ...
    return str(repo_path), "EXACT_SHA"
```

## Key Invariants Tested

The test suite validates these critical invariants:

1. **Read-Only Guarantee**: `git status --porcelain` is clean before AND after analysis
2. **Exact SHA Enforcement**: Fake/invalid SHAs raise `RuntimeError`
3. **Dirty Working Tree Prevention**: Modified working trees before checkout raise `RuntimeError`
4. **Output Schema Compliance**: Result has all 9 required keys (`repo`, `sha`, `role`, `root_cause`, `affected_component`, `evidence`, `confidence`, `uncertainty`, `recommended_next_action`)
5. **SHA Grounding**: Returned SHA matches the exact checkout SHA

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Working tree not clean before analysis" | Repo has uncommitted changes | `git commit` or `git stash` all changes |
| "Failed to checkout SHA" | SHA doesn't exist in repo history | Use `git rev-parse HEAD` to get the correct SHA |
| "Empty response from LLM" | No OpenAI API credentials configured | Provide valid `RCA_API_KEY`, `RCA_API_BASE_URL`, `RCA_MODEL_NAME` |
| "Missing required field in LLM response" | LLM output missing schema fields | Ensure the analysis outputs valid JSON per the schema |