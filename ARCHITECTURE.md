# Architecture Specification

- Front-End: Streamlit Chat UI (`app.py`) with file upload for SOW (.md) and Failure Evidence (.txt/.log).
- Engine: `rca_engine.py` orchestrating Git checkouts, Aider RepoMap generation, context assembly, and OpenAI/OpenHands reasoning.
- Context Pipeline: SOW + README.md + AGENTS.md + Aider RepoMap + Failure Evidence + Target SHA.
- Safety & Integrity: Pre- and post-execution `git status --porcelain` validation to enforce the read-only rule.
- Tests: `tests/test_rca.py` validating SHA grounding, read-only guarantees, and structured JSON generation.