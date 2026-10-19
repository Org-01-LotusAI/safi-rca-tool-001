# AGENTS.md - Repository Conventions & Invariants

## Architecture Guidelines
- System follows layered boundaries: API / Runner -> Orchestrator -> Domain Diagnostic -> Inspection Tools.
- Invariants: Null-checks and missing record validations must be explicit.
- Operations: All agent executions must remain strictly READ-ONLY.

## Agent Operating Rules
- Never modify existing files or commit code during diagnostic runs.
- Use git plumbing (`git status --porcelain`) before and after operations to verify working tree immutability.
- Always tie analysis output to the exact Git commit SHA specified.