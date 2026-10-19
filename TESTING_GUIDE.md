# Testing Guide for SAFI RCA Tool

This guide covers how to test the SAFI Root Cause Analyzer tool, run the existing test suite, and create demo repositories for manual testing.

## Section 1: Running the Existing Test Suite

### Prerequisites

```bash
# From the project root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements pytest pytest-mock
```

### Run All Tests

```bash
pytest tests/ -v
```

**Output:**
```
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- /Library/Developer/CommandLineTools/usr/bin/python3
cachedir: .pytest_cache
rootdir: /Users/hirak/MEGA/Developer/free/safi-rca-tool
plugins: mock-3.15.1
collected 12 items

tests/test_rca.py::test_read_only_invariant PASSED                       [  8%]
tests/test_rca.py::test_verify_and_prep_git_read_only PASSED             [ 16%]
tests/test_rca.py::test_exact_sha_enforcement_fake_sha PASSED            [ 25%]
tests/test_rca.py::test_verify_and_prep_git_fake_sha_raises PASSED       [ 33%]
tests/test_rca.py::test_exact_sha_enforcement_dirty_working_tree PASSED  [ 41%]
tests/test_rca.py::test_output_schema PASSED                             [ 50%]
tests/test_rca.py::test_output_schema_with_partial_llm_response PASSED   [ 58%]
tests/test_rca.py::test_generate_repomap_runs PASSED                     [ 66%]
tests/test_rca.py::test_get_repo_file_reads_existing PASSED              [ 75%]
tests/test_rca.py::test_get_repo_file_missing_returns_empty PASSED       [ 83%]
tests/test_rca.py::test_verify_and_prep_git_not_a_git_repo PASSED        [ 91%]
tests/test_rca.py::test_full_pipeline_integration PASSED                 [100%]

============================== 12 passed in ~2.5s ==============================
```

### Test Categories

The 12 tests cover these invariant groups:

| Test Name | Category | What It Validates |
|-----------|----------|-------------------|
| `test_read_only_invariant` | Read-only | Git status clean before AND after analysis |
| `test_verify_and_prep_git_read_only` | Git validation | `verify_and_prep_git()` enforces clean working tree |
| `test_exact_sha_enforcement_fake_sha` | SHA enforcement | Fake SHA raises `RuntimeError` |
| `test_verify_and_prep_git_fake_sha_raises` | SHA enforcement | Direct `verify_and_prep_git()` with fake SHA |
| `test_exact_sha_enforcement_dirty_working_tree` | SHA + clean tree | Dirty tree before checkout raises `RuntimeError` |
| `test_output_schema` | Schema compliance | All 9 required keys present, SHA matches |
| `test_output_schema_with_partial_llm_response` | Schema validation | Missing fields raise `RuntimeError` |
| `test_generate_repomap_runs` | Helper functions | `generate_repomap()` executes without crash |
| `test_get_repo_file_reads_existing` | Helper functions | Reading existing files works |
| `test_get_repo_file_missing_returns_empty` | Helper functions | Missing files return empty string |
| `test_verify_and_prep_git_not_a_git_repo` | Edge cases | Non-git directory raises `RuntimeError` |
| `test_full_pipeline_integration` | Integration | End-to-end pipeline with mocked LLM |

## Section 2: Creating a Demo Repository for Manual Testing

### Manual Demo Repo Creation (Step-by-Step)

```bash
# 1. Create a fresh directory
mkdir demo_repo && cd demo_repo

# 2. Initialize a git repository
git init

# 3. Configure git identity
git config user.name "Test User"
git config user.email "test@example.com"

# 4. Create README.md
cat > README.md << 'EOF'
# Payment Core Service
EOF

# 5. Create AGENTS.md (required by the tool's architecture)
cat > AGENTS.md << 'EOF'
# Architecture
Validators must guard null lookups before property access.
EOF

# 6. Create source code with a deliberate bug
mkdir -p src
cat > src/validator.py << 'EOF'
def validate_transaction(user_record):
    # Deliberate root cause bug: unhandled null customer record dereference
    return user_record.get("balance") > 0
EOF

# 7. Add and commit all files
git add .
git commit -m "Initial commit with validator bug"

# 8. Get the exact SHA (critical for RCA analysis)
EXACT_SHA=$(git rev-parse HEAD)
echo "Exact SHA: $EXACT_SHA"

# 9. Create failure evidence file
cat > evidence.txt << 'EOF'
Traceback (most recent call last):
  File "src/main.py", line 42, in process_payment
    if validate_transaction(user):
  File "src/validator.py", line 3, in validate_transaction
    return user_record.get("balance") > 0
AttributeError: 'NoneType' object has no attribute 'get'
EOF

# 10. (Optional) Create a SOW file
cat > sow.md << 'EOF'
# Statement of Work: Payment Service

## Requirements
1. Validate transaction before processing
2. Handle null customer records gracefully
3. Return appropriate error messages for invalid states
EOF

# 11. Verify the structure
find . -type f | sort
```

### Demo Repo Verification

After creation, verify:

```bash
# Check the SHA
git rev-parse HEAD

# Verify git status is clean
git status --porcelain
# Should output nothing (empty)

# Check file contents
cat src/validator.py
cat evidence.txt
```

### Using the Demo Repo with the RCA Tool

#### CLI Usage

```bash
# From the safi-rca-tool directory
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure API credentials (required even for mocked tests)
export RCA_MODEL_NAME="Nemotron 3 Ultra"
export RCA_API_BASE_URL="https://your-endpoint/v1"
export RCA_API_KEY="sk-..."  # Use a placeholder or valid key

# Run analysis
python3 rca_engine.py analyze \
  --repo ./demo_repo \
  --sha "$EXACT_SHA" \
  --evidence ./evidence.txt \
  --sow ./sow.md
```

Expected successful output (JSON to stdout):

```json
{
  "repo": "/absolute/path/to/demo_repo",
  "sha": "a1b2c3d4e5f6...",
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
```

#### Streamlit Web UI Usage

```bash
streamlit run app.py
# Open http://localhost:8501 in your browser
```

In the sidebar:
1. Enter the demo repo path (e.g., `/absolute/path/to/demo_repo`)
2. Enter the exact SHA (e.g., `a1b2c3d4e5f6...`)
3. Upload the `evidence.txt` file
4. (Optional) Upload the `sow.md` file
5. Click **"Run Root Cause Analysis"**

## Section 3: Adding a Demo Repo to the Test Suite

If you want to add your demo repo as a pytest fixture for the test suite:

1. Create a new fixture in `tests/test_rca.py` or extend the existing `mock_failing_repo`:

```python
@pytest.fixture
def my_demo_repo(tmp_path):
    """
    Create a demo repository for manual testing.
    
    Returns:
        tuple: (repo_path: str, exact_sha: str)
    """
    repo_path = tmp_path / "my_demo"
    repo_path.mkdir()
    
    import subprocess
    
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
    
    # Create required files
    (repo_path / "README.md").write_text("# Test Repository\n")
    (repo_path / "AGENTS.md").write_text("# Architecture\nNull guards required.\n")
    
    src_dir = repo_path / "src"
    src_dir.mkdir()
    (src_dir / "validator.py").write_text("""
def validate_transaction(user_record):
    # Bug: unhandled null
    return user_record.get("balance") > 0
""")
    
    # Commit
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path, check=True, capture_output=True
    )
    
    # Get SHA
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, check=True, capture_output=True, text=True
    )
    exact_sha = result.stdout.strip()
    
    return str(repo_path), exact_sha
```

2. Use the fixture in your tests:

```python
def test_with_my_demo_repo(my_demo_repo, sample_evidence, mock_llm_response):
    repo_path, exact_sha = my_demo_repo
    # ... test logic
```

## Section 4: Testing Checklist

### For Manual Testing with Demo Repo

- [ ] Demo repo has valid git history with a known SHA
- [ ] `git status --porcelain` returns empty (clean working tree)
- [ ] Failure evidence file contains a stack trace with file:line references
- [ ] Optional SOW file is valid markdown (if testing SOW context)
- [ ] RCA CLI produces valid JSON output with all 9 required keys
- [ ] Web UI renders the RCA report correctly
- [ ] Confidence level is one of: High, Medium, Low
- [ ] Recommended next action is meaningful and non-empty

### For Test Suite Contributions

- [ ] New test follows existing fixture patterns (`mock_failing_repo`)
- [ ] Test maintains the read-only invariant (no git modifications)
- [ ] Test uses mocked LLM responses for reliable offline execution
- [ ] Test covers a specific invariant not already tested
- [ ] All existing tests still pass after adding new tests
- [ ] Test is documented in the test categories table