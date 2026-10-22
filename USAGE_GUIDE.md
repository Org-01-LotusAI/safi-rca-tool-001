# SAFI Root Cause Analyzer - Usage Guide

## Overview

The **SAFI Root Cause Analyzer** is a production-grade diagnostic system that:

- Binds analysis to an exact Git commit SHA
- Assembles full repository context (SOW, README, AGENTS.md, RepoMap, failure evidence)
- Invokes a deterministic LLM to distinguish root cause from symptom
- Produces structured JSON output with confidence scores and recommended next actions
- Enforces read-only operations (git status validated before AND after analysis)

## What Problem It Solves

This tool answers two key questions:

1. **Has the developer made the product as per the SOW?** - By comparing the failure evidence and code state against the Statement of Work requirements at the specified commit.

2. **Are all tests passing?** - The engine includes 12 acceptance tests verifying: read-only invariant, SHA enforcement, output schema compliance, and full pipeline integration.

## Quick Start

### Prerequisites

```bash
# Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# Key packages: openai, streamlit, pytest, pytest-mock, aider-chat
```

### Configure Environment Variables

```bash
export RCA_MODEL_NAME="Nemotron 3 Ultra"
export RCA_API_BASE_URL="https://your-endpoint/v1"
export RCA_API_KEY="sk-..."
```

### Option 1: CLI Analysis

```bash
python rca_engine.py analyze \
  --repo /path/to/your/repo \
  --sha 8f51ab2d3c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8 \
  --evidence ./error.log \
  --sow ./SOW.md
```

### Option 2: Web UI (Streamlit)

```bash
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

## Step-by-Step: Using the Web UI

### 1. Provide Target Repository Path

In the sidebar, enter the absolute path to your Git repository (e.g., `/Users/hirak/MEGA/Developer/my-project`).

### 2. Provide Exact Git SHA

Enter the precise commit hash to analyze (e.g., `8f51ab2`). This anchors the analysis to a specific code state.

### 3. Upload Failure Evidence

Upload a `.txt` or `.log` file containing error traces, stack traces, or failure logs. This is **required**.

Example evidence content:
```
Traceback (most recent call last):
  File "src/main.py", line 42, in process_payment
    if validate_transaction(user):
  File "src/validator.py", line 3, in validate_transaction
    return user_record.get("balance") > 0
AttributeError: 'NoneType' object has no attribute 'get'
```

### 4. Optional: Upload Statement of Work (SOW)

Upload a `.md` file with requirements/SOW. This helps the LLM understand what the product was supposed to do.

Example SOW (`sow.md`):
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

### 5. Click "Run Root Cause Analysis"

Press the primary **Run Root Cause Analysis** button. The system will:

1. ✅ Verify the repo is a valid Git work tree
2. ✅ Check working tree is clean before checkout
3. ✅ Checkout the exact SHA
4. ✅ Generate Aider RepoMap
5. ✅ Read: README.md, AGENTS.md, skill files
6. ✅ Build prompts with full context
7. ✅ Invoke LLM (temperature 0.1, JSON-only)
8. ✅ Validate output schema
9. ✅ Reset working tree to original SHA
10. ✅ Display structured RCA report

### 6. Review the RCA Report

The report includes:

| Section | Description |
|---------|-------------|
| **Target SHA** | The commit hash analyzed |
| **Confidence** | High/Medium/Low badge |
| **Affected Component** | File:function where the issue exists |
| **Root Cause** | The underlying defect (not just symptoms) |
| **Evidence** | File paths and log excerpts supporting the diagnosis |
| **Uncertainty** | Any unverified assumptions |
| **Recommended Next Action** | Concrete fix strategy |

### 7. Download JSON Report

Use the **Download RCA JSON Report** button to save the full result for CI/CD integration.

### 8. Follow-up Questions

After analysis, you can ask follow-up questions in the chat input, such as:
- "What exact line causes the null dereference?"
- "How does this relate to the SOW requirements?"
- "What's the recommended fix strategy?"

Responses are grounded in the RCA result and cannot contradict it.

## Directory Structure

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
└── README.md               # This documentation
```

## How It Works (Internal Flow)

```mermaid
flowchart TD
    A[Input: Repo Path + SHA + Evidence + SOW] --> B{verify_and_prep_git()}
    B -->|Validate repo| C[Checkout exact SHA]
    C --> D[Generate Aider RepoMap]
    D --> E[Read repo files: README.md, AGENTS.md, skills]
    E --> F[Build system + user prompts]
    F --> G[Invoke LLM: temperature=0.1, JSON-only]
    G --> H[Parse & validate JSON response]
    H --> I{Validate post-execution git status}
    I -->|Clean| J[Enrich result: set repo, sha, role]
    I -->|Dirty| K[Reset to original SHA + raise error]
    J --> L[Return structured RCA result]
```

## Test Suite

Run the 12 acceptance tests:

```bash
pytest tests/ -v
```

**Tests cover:**
- ✅ Read-only invariant (git status clean before AND after)
- ✅ Exact SHA enforcement (fake SHA rejected)
- ✅ Output schema compliance (9 required keys)
- ✅ Helper functions (RepoMap, file reading, git validation)
- ✅ Full pipeline integration (end-to-end with mocked LLM)

## Key Invariants

| Invariant | Description |
|-----------|-------------|
| **Zero Mutations** | Git working tree verified clean before and after every run |
| **SHA Grounding** | All findings tied to exact commit hash |
| **Deterministic** | Temperature 0.1, JSON-only output |
| **Auditable** | Complete context + result exported as JSON |

## Configuration

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `RCA_MODEL_NAME` | Yes | — | Model identifier (e.g., "Nemotron 3 Ultra") |
| `RCA_API_BASE_URL` | Yes | — | OpenAI-compatible API endpoint |
| `RCA_API_KEY` | Yes | — | API authentication key |
| `RCA_TIMEOUT` | No | 120 | Request timeout in seconds |

## Example: Full End-to-End

```bash
# 1. Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
export RCA_MODEL_NAME="Nemotron 3 Ultra"
export RCA_API_BASE_URL="https://your-endpoint/v1"
export RCA_API_KEY="sk-..."

# 3. Run via CLI
python rca_engine.py analyze \
  --repo /path/to/repo \
  --sha abc123def456 \
  --evidence ./error.log \
  --sow ./SOW.md

# 4. Or via UI: streamlit run app.py
```