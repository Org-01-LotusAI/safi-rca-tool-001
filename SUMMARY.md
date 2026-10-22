# SAFI Root Cause Analyzer - Summary

## What This Codebase Does

The **SAFI Root Cause Analyzer** is a diagnostic system that analyzes Git repositories to identify the root cause of software defects. It answers two critical questions:

1. **Has the developer made the product as per the SOW?** - By comparing the code state, failure evidence, and Statement of Work requirements at a specific commit.

2. **Are all tests passing / is the code correct?** - Through 12 acceptance tests that verify the engine's core invariants.

## Core Engine (`rca_engine.py`)

The engine orchestrates the full RCA pipeline:

### Key Functions

| Function | Purpose |
|---|---|
| `verify_and_prep_git(repo_path, sha)` | Validates repo is a Git work tree, checkouts exact SHA, ensures clean working tree before/after |
| `generate_repomap(repo_path)` | Runs `aider --no-git --show-repo-map` to generate repository structure map |
| `get_repo_file(repo_path, filename)` | Safely reads root-level files (README.md, AGENTS.md) |
| `build_system_prompt()` | Builds the system prompt for the LLM (strict directives for root cause analysis) |
| `build_user_prompt(...)` | Assembles all context: SOW, evidence, README, AGENTS.md, skill, RepoMap |
| `run_rca_analysis(...)` | Full pipeline: git prep → context → LLM invoke → schema validation → tree reset |
| `format_rca_report(result)` | Formats result as structured Markdown for display |
| `print_terminal_summary(result)` | Human-readable summary to stderr (CLI) |

### Pipeline Flow

```
Inputs (repo path + SHA + evidence + SOW)
    ↓
verify_and_prep_git(): Validate repo, checkout SHA, check clean tree
    ↓
generate_repomap(): Aidér repo-map generation
    ↓
Read repo files: README.md, AGENTS.md, .agents/skills/root-cause-analyzer.md
    ↓
Build prompts with full context (SOW + evidence + repo files + RepoMap)
    ↓
Invoke LLM: temperature=0.1, JSON-only response_format
    ↓
Parse & validate JSON response schema (9 required fields)
    ↓
Validate post-execution git status (ensure read-only)
    ↓
Enrich result: set repo, sha, role fields
    ↓
Return structured RCA result JSON
```

## Web UI (`app.py`)

Streamlit-based chat interface with:

- **Sidebar**: Repo path, SHA, SOW upload, evidence upload
- **Primary action**: "Run Root Cause Analysis" button
- **Rendered report**: Structured Markdown with confidence badge, affected component, root cause, evidence, uncertainty, next action
- **Download button**: JSON report export
- **Follow-up chat**: Questions grounded in the RCA result (cannot contradict findings)

### UI Steps

1. Enter target repo path (e.g., `/path/to/repo`)
2. Enter exact Git SHA (e.g., `8f51ab2`)
3. Upload failure evidence (.txt or .log file, **required**)
4. Optionally upload SOW (.md file)
5. Click "Run Root Cause Analysis"
6. Review the structured report
7. Download JSON report if needed
8. Ask follow-up questions in chat

## Statement of Work (`demo_repo/sow.md`)

Defines the requirements the product should meet:

```
# Statement of Work: Payment Service

## Overview
The payment service must handle user records securely, including null user records.

## Requirements
1. Validate transaction before processing
2. Handle null customer records gracefully
3. Return appropriate error messages for invalid states
4. Maintain audit logs for all transactions
```

## Failure Evidence (`demo_repo/evidence.txt`)

Example failure trace:

```
Traceback (most recent call last):
  File "src/main.py", line 42, in process_payment
    if validate_transaction(user):
  File "src/validator.py", line 3, in validate_transaction
    return user_record.get("balance") > 0
AttributeError: 'NoneType' object has no attribute 'get'
```

## Deliberate Bug (`demo_repo/src/validator.py`)

```python
def validate_transaction(user_record):
    # Deliberate root cause bug: unhandled null customer record dereference
    return user_record.get("balance") > 0
```

This demonstrates the pattern the tool detects: **null record dereference without null guard**.

## Architecture (`demo_repo/AGENTS.md`)

```
# Architecture
Validators must guard null lookups before property access.
```

## Repository Structure

```
safi-rca-tool/
├── app.py                  # Streamlit Web UI
├── rca_engine.py           # Core backend engine
├── tests/test_rca.py       # 12 acceptance tests
├── demo_repo/              # Example repository for testing
│   ├── sow.md              # Statement of Work
│   ├── evidence.txt        # Failure evidence
│   ├── README.md           # Repository README
│   ├── AGENTS.md           # Architecture guidelines
│   └── src/validator.py    # Example code with deliberate bug
├── .agents/skills/root-cause-analyzer.md  # Analyzer skill definition
├── ARCHITECTURE.md         # Architecture specification
├── AGENTS.md               # Repository conventions
└── README.md               # Quick start documentation
```

## Test Suite (12 Tests)

All tests in `tests/test_rca.py` verify core invariants:

| Test Category | What It Verifies |
|---|---|
| **Read-only invariant** | git status clean before AND after analysis |
| **Exact SHA enforcement** | Fake/non-existent SHA raises RuntimeError |
| **Dirty working tree** | Modified tree before checkout rejected |
| **Output schema compliance** | All 9 required JSON keys present |
| **Helper functions** | RepoMap generation, file reading, git validation |
| **Full pipeline integration** | End-to-end with mocked LLM |

### Required JSON Schema (9 fields)

```json
{
  "repo": "<repo-path>",
  "sha": "<exact-git-sha>",
  "role": "root-cause-analyzer",
  "root_cause": "<root cause summary>",
  "affected_component": "<file:function>",
  "evidence": ["<path:line>", "<log excerpt>"],
  "confidence": "High | Medium | Low",
  "uncertainty": "<details or None>",
  "recommended_next_action": "<action recommendation>"
}
```

## How It Solves Your Problem

### Does the product meet the SOW?

The tool analyzes the code at the specified SHA against:

1. **SOW requirements** (uploaded as .md file) - What the product was supposed to do
2. **Failure evidence** (uploaded as .txt/.log) - What actually went wrong
3. **Code at that commit** - The actual implementation

It then identifies whether the root cause aligns with SOW compliance. For example, with the demo repo:

- SOW says: "Handle null customer records gracefully"
- Evidence shows: `AttributeError: 'NoneType' object has no attribute 'get'`
- Code shows: `user_record.get("balance")` without null check
- **Root cause**: Missing null guard before property access (violates SOW requirement #2)

### Are tests passing?

The codebase includes **12 acceptance tests** that verify:

- ✅ Read-only invariant (git status clean before/after)
- ✅ Exact SHA enforcement (fake SHA rejected with error)
- ✅ Output schema compliance (9 required keys validated)
- ✅ Helper functions work correctly
- ✅ Full pipeline integration (end-to-end)

All tests should pass when run: `pytest tests/ -v`

## Configuration

Required environment variables:

| Env Var | Required | Description |
|---|---|---|
| `RCA_MODEL_NAME` | Yes | Model identifier (e.g., "Nemotron 3 Ultra") |
| `RCA_API_BASE_URL` | Yes | OpenAI-compatible API endpoint |
| `RCA_API_KEY` | Yes | API authentication key |

Optional:

| Env Var | Default | Description |
|---|---|---|
| `RCA_TIMEOUT` | 120 | Request timeout in seconds |

## Quick Start Commands

### CLI Analysis

```bash
python rca_engine.py analyze \
  --repo /path/to/repo \
  --sha abc123def456 \
  --evidence error.log \
  --sow sow.md
```

### Web UI

```bash
streamlit run app.py
# Then open http://localhost:8501
```

### Run Tests

```bash
pytest tests/ -v
```

## Key Invariants Enforced

| Invariant | Description |
|---|---|
| **Zero Mutations** | Git working tree verified clean before and after every run |
| **SHA Grounding** | All findings tied to exact commit hash |
| **Deterministic** | Temperature 0.1, JSON-only output |
| **Auditable** | Complete context + result exported as JSON |
| **Read-Only** | No code edits, no file modifications during analysis |