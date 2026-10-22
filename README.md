# SAFI Root Cause Analyzer (Product 010)

> **Trainable Root Cause Analyzer** — A production-grade, read-only diagnostic system that binds to an exact Git SHA, assembles full repository context, and invokes a deterministic LLM to distinguish root cause from symptom.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/Tests-12%20passing-brightgreen.svg)](tests/test_rca.py)
[![License](https://img.shields.io/badge/License-Internal-lightgrey.svg)](#)

---

## 🎯 Quick Start

```bash
# 1. Setup
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install aider-chat

# 2. Configure (required)
export RCA_MODEL_NAME="Nemotron 3 Ultra"
export RCA_API_BASE_URL="https://your-endpoint/v1"
export RCA_API_KEY="sk-..."

# 3. Run CLI Analysis
# Support for both local paths and Git remote URLs:
#   - Local path: /path/to/repo
#   - Git URL: https://github.com/username/repo.git or git@github.com:username/repo.git
python rca_engine.py analyze \
  --repo /path/to/your/repo \
  --sha 8f51ab2d3c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8 \
  --evidence ./error.log \
  --sow ./SOW.md

# 4. Or Launch Web UI
streamlit run app.py
```

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **Exact SHA Binding** | Analysis cryptographically bound to a specific commit |
| **Read-Only Guarantee** | Dual `git status --porcelain` validation (pre/post) |
| **Full Context Assembly** | SOW + README + AGENTS.md + Skill + RepoMap + Evidence |
| **Deterministic LLM** | Temperature 0.1, JSON-only output, structured schema |
| **Dual Interface** | CLI (`rca_engine.py`) + Web Chat (`app.py`) |
| **Audit-Ready JSON** | Machine-readable output for CI/CD integration |
| **Interactive Follow-Up** | Chat with the diagnosis grounded in RCA result |

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Inputs    │────▶│   RCA Engine     │────▶│   Outputs       │
├─────────────┤     ├──────────────────┤     ├─────────────────┤
│ • Repo Path │     │ 1. Git Ops       │     │ • JSON Report   │
│ • Git SHA   │     │ 2. Context       │     │ • Terminal Sum  │
│ • Evidence  │     │    Assembly      │     │ • Downloadable  │
│ • SOW (opt) │     │ 3. LLM Invoke    │     │   JSON File     │
└─────────────┘     │ 4. Validation    │     │ • Chat History  │
                    └──────────────────┘     └─────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Context Pipeline     │
              ├────────────────────────┤
              │ • Failure Evidence     │
              │ • SOW (optional)       │
              │ • README.md            │
              │ • AGENTS.md            │
              │ • Root Cause Skill     │
              │ • Aider RepoMap        │
              └────────────────────────┘
```

---

## 📋 JSON Output Schema

```json
{
  "repo": "/absolute/path/to/repo",
  "sha": "8f51ab2d3c4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
  "role": "root-cause-analyzer",
  "root_cause": "Null pointer dereference in validate_transaction when user_record is None",
  "affected_component": "src/validator.py:validate_transaction",
  "evidence": [
    "src/validator.py:3",
    "AttributeError: 'NoneType' object has no attribute 'get'"
  ],
  "confidence": "High",
  "uncertainty": "None",
  "recommended_next_action": "Add null check: if user_record is None: return False"
}
```

---

## 🧪 Acceptance Tests

```bash
pytest tests/ -v
```

**12 Tests Covering:**
- ✅ Read-Only Invariant (pre/post git status clean)
- ✅ Exact SHA Enforcement (fake SHA, dirty tree rejected)
- ✅ Output Schema Compliance (9 required keys, SHA match)
- ✅ Helper Functions (RepoMap, file reading, git validation)
- ✅ Full Pipeline Integration (end-to-end with mocked LLM)

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| [DOCS.md](DOCS.md) | Complete system documentation (architecture, setup, CLI, UI, testing) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture specification |
| [AGENTS.md](AGENTS.md) | Repository conventions & invariants |
| [.agents/skills/root-cause-analyzer.md](.agents/skills/root-cause-analyzer.md) | Role training / skill definition |

---

## 🔧 Configuration

| Env Var | Required | Default | Description |
|---------|----------|---------|-------------|
| `RCA_MODEL_NAME` | Yes | — | Model identifier (e.g., "Nemotron 3 Ultra") |
| `RCA_API_BASE_URL` | Yes | — | OpenAI-compatible API endpoint |
| `RCA_API_KEY` | Yes | — | API authentication key |
| `RCA_TIMEOUT` | No | 120 | Request timeout in seconds |

---

## 🛡️ Safety & Integrity

- **Zero Mutations**: Git working tree verified clean before and after every run
- **SHA Grounding**: All findings tied to exact commit hash
- **Deterministic**: Temperature 0.1, JSON-only output
- **Auditable**: Complete context + result exported as JSON

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `openai` | LLM client (OpenAI-compatible) |
| `streamlit` | Web chat interface |
| `pytest` + `pytest-mock` | Testing framework |
| `aider-chat` | RepoMap generation (external) |

---

## 🤝 Contributing

1. All changes must pass `pytest tests/ -v`
2. Maintain read-only invariant in any engine modifications
3. Update DOCS.md for architectural changes
4. Follow AGENTS.md conventions

---

## 📄 License

Internal Tooling — SAFI Product 010

---

*Built with OpenHands Agent Runtime, Aider, Nemotron 3 Ultra, Streamlit*