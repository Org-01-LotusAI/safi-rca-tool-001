#!/usr/bin/env python3
"""
Core Backend Engine for Root Cause Analysis (RCA).

This module provides the orchestration layer for analyzing failures in Git repositories.
It handles Git operations, Aider RepoMap generation, context assembly, and LLM-based
root cause diagnosis using Nemotron 3 Ultra.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed, rely on shell env

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


@dataclass
class RCAConfig:
    """Configuration for RCA analysis."""
    model_name: str = "Nemotron 3 Ultra"
    temperature: float = 0.1
    base_url: Optional[str] = None
    api_key: Optional[str] = None


# Default configuration - can be overridden via environment variables
DEFAULT_CONFIG = RCAConfig(
    model_name=os.getenv("RCA_MODEL_NAME", "Nemotron 3 Ultra"),
    temperature=0.1,
    base_url=os.getenv("RCA_API_BASE_URL"),
    api_key=os.getenv("RCA_API_KEY"),
)


def _clone_repo_from_url(repo_url: str, target_dir: str) -> None:
    """
    Clone a Git repository from a URL to a target directory.

    Args:
        repo_url: The Git repository URL (https, ssh, etc.)
        target_dir: Directory where the repo should be cloned.
    """
    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repository from '{repo_url}': {result.stderr}")


def _is_git_url(path: str) -> bool:
    """Check if the given path looks like a Git remote URL."""
    # Check for standard Git URL protocols
    if path.startswith("http://") or path.startswith("https://") or \
       path.startswith("git://") or path.startswith("git+") or \
       "@" in path and (path.startswith("ssh://") or path.startswith("git@")) or \
       path.startswith("file://"):
        return True
    # Also accept URLs with single slash after protocol (e.g., https:/host)
    # Normalize by checking if it starts with a protocol followed by :
    import re
    # Match patterns like http:/, https:/, git:/, file:/
    if re.match(r'^[a-zA-Z+]+:/', path):
        return True
    return False


def verify_and_prep_git(repo_path: str, sha: str) -> Tuple[str, bool]:
    """
    Validate that repo_path is a Git work tree, checkout the exact SHA,
    and assert that the working tree is clean before starting.

    Supports both local Git repository paths and Git remote URLs.
    If a URL is provided, the repo will be cloned to a temporary directory
    and that directory will be returned (caller is responsible for cleanup).

    Args:
        repo_path: Path to the Git repository or Git remote URL.
        sha: Exact Git commit SHA to checkout.

    Returns:
        Tuple of (repo_path_or_clone_dir, was_cloned_from_url)

    Raises:
        RuntimeError: If the repo cannot be set up, checkout fails,
                      or working tree is dirty.
    """
    was_cloned = False
    repo_url = None

    # Check if input is a Git URL that needs cloning
    if _is_git_url(repo_path):
        # Create a temporary directory for the cloned repo
        tmp_dir = tempfile.mkdtemp(prefix="safi_rca_")
        try:
            _clone_repo_from_url(repo_path, tmp_dir)
        except RuntimeError as e:
            raise e
        repo_path = tmp_dir
        was_cloned = True
        repo_url = repo_path  # Save original URL for cleanup tracking

    repo_path = os.path.abspath(repo_path)

    # Check if it's a Git work tree
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        # If we cloned from a URL, clean up
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise RuntimeError(f"Path '{repo_path}' is not a valid Git work tree.")

    # Check working tree is clean BEFORE checkout
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        # If we cloned from a URL, clean up before raising
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise RuntimeError(
            f"Working tree at '{repo_path}' is not clean before checkout. "
            f"Please commit or stash changes first.\n{result.stdout}"
        )

    # Checkout the exact SHA
    result = subprocess.run(
        ["git", "checkout", sha],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # If we cloned from a URL, clean up before raising
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise RuntimeError(f"Failed to checkout SHA '{sha}': {result.stderr}")

    # Verify working tree is clean AFTER checkout
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        # If we cloned from a URL, clean up before raising
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise RuntimeError(
            f"Working tree at '{repo_path}' is not clean after checkout of '{sha}'.\n{result.stdout}"
        )

    return repo_path, was_cloned


def generate_repomap(repo_path: str, timeout: int = 120) -> str:
    """
    Run `aider --no-git --show-repo-map` to generate a repository map.

    Args:
        repo_path: Path to the Git repository.
        timeout: Maximum time in seconds to wait for aider to complete.

    Returns:
        The repo map output as a string, or empty string on failure.
    """
    try:
        result = subprocess.run(
            ["aider", "--no-git", "--show-repo-map"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Clean up aider's chat history file if it was created
        aider_history = Path(repo_path) / ".aider.chat.history.md"
        if aider_history.exists():
            try:
                aider_history.unlink()
            except Exception:
                pass  # Best effort cleanup
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            # aider might output to stderr on some errors but still produce useful map
            return result.stdout.strip() or result.stderr.strip()
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] Aider repo-map generation exceeded {timeout} seconds."
    except FileNotFoundError:
        return "[ERROR] 'aider' command not found. Please install aider."
    except Exception as e:
        return f"[ERROR] Failed to generate repo-map: {str(e)}"


def get_repo_file(repo_path: str, filename: str) -> str:
    """
    Safely read a root repository file if present.

    Args:
        repo_path: Path to the Git repository.
        filename: Name of the file to read (e.g., 'README.md', 'AGENTS.md').

    Returns:
        File contents as string, or empty string if file doesn't exist.
    """
    file_path = Path(repo_path) / filename
    if file_path.is_file():
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def build_system_prompt() -> str:
    """Build the system prompt for the root cause analyzer."""
    return """You are an expert Root Cause Analyzer for software defects.

MISSION: Analyze failure logs, Git repository files, SOW constraints, and Aider RepoMap to diagnose the UNDERLYING ROOT CAUSE of a defect.

STRICT DIRECTIVES:
1. READ-ONLY: Inspect, grep, and read files only. NEVER edit, write, or patch code.
2. DISTINGUISH SYMPTOM vs ROOT CAUSE: Do not echo "HTTP 500" or assertion lines. Identify the exact logic or code defect.
3. CITE CONCRETE EVIDENCE: Include file paths, line references, function/class names, and relevant test or log lines.
4. EXPRESS UNCERTAINTY: Use "High", "Medium", or "Low" confidence. Explicitly outline any unverified assumptions.
5. ACTIONABLE NEXT ACTION: Detail the fix strategy without executing it.

OUTPUT FORMAT: Return ONLY a valid JSON object matching this exact schema:
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
}"""


def build_user_prompt(
    repo_path: str,
    sha: str,
    evidence: str,
    sow_content: str,
    readme_content: str,
    agents_content: str,
    skill_content: str,
    repomap: str,
) -> str:
    """Build the user prompt with all context for the LLM."""
    return f"""REPOSITORY: {repo_path}
TARGET SHA: {sha}

=== FAILURE EVIDENCE ===
{evidence}

=== STATEMENT OF WORK (SOW) ===
{sow_content if sow_content else "(Not provided)"}

=== README.md ===
{readme_content if readme_content else "(Not found)"}

=== AGENTS.md ===
{agents_content if agents_content else "(Not found)"}

=== ROOT CAUSE ANALYZER SKILL ===
{skill_content}

=== AIDER REPO MAP ===
{repomap if repomap else "(Not available)"}

TASK: Analyze the above context and diagnose the ROOT CAUSE of the failure.
Return ONLY the JSON response per the schema in the system prompt."""


def create_openai_client(config: RCAConfig) -> "OpenAI":
    """Create and configure the OpenAI-compatible client."""
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client_kwargs = {}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    if config.api_key:
        client_kwargs["api_key"] = config.api_key

    return OpenAI(**client_kwargs)


def run_rca_analysis(
    repo_path: str,
    sha: str,
    evidence: str,
    sow_content: str = "",
    config: Optional[RCAConfig] = None,
) -> dict:
    """
    Run the full RCA analysis pipeline.

    Args:
        repo_path: Path to the Git repository or Git remote URL.
        sha: Exact Git commit SHA to analyze.
        evidence: Failure evidence text (logs, stack traces, etc.).
        sow_content: Optional Statement of Work content.
        config: Optional RCAConfig for model settings.

    Returns:
        Parsed dictionary matching the RCA output schema.

    Raises:
        RuntimeError: If Git operations fail, working tree is modified,
                      or LLM response is invalid.
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Step 1: Verify and prep Git (supports both local paths and URLs)
    # Returns (repo_path, was_cloned_from_url)
    repo_path, was_cloned = verify_and_prep_git(repo_path, sha)

    try:
        # Step 2: Gather context
        readme_content = get_repo_file(repo_path, "README.md")
        agents_content = get_repo_file(repo_path, "AGENTS.md")
        skill_path = Path(repo_path) / ".agents" / "skills" / "root-cause-analyzer.md"
        skill_content = skill_path.read_text(encoding="utf-8") if skill_path.is_file() else ""
        repomap = generate_repomap(repo_path)

        # Step 3: Build prompts
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            repo_path=repo_path,
            sha=sha,
            evidence=evidence,
            sow_content=sow_content,
            readme_content=readme_content,
            agents_content=agents_content,
            skill_content=skill_content,
            repomap=repomap,
        )

        # Step 4: Invoke LLM
        client = create_openai_client(config)
        response = client.chat.completions.create(
            model=config.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.temperature,
            response_format={"type": "json_object"},
        )

        # Step 5: Parse response
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Empty response from LLM")

        result = json.loads(content)

        # Step 6: Validate post-execution working tree
        # Clean up aider history file that may have been created during repo-map generation
        aider_history = Path(repo_path) / ".aider.chat.history.md"
        if aider_history.exists():
            try:
                aider_history.unlink()
            except Exception:
                pass  # Best effort cleanup

        git_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if git_status.stdout.strip():
            # Reset to the original SHA
            subprocess.run(
                ["git", "reset", "--hard", sha],
                cwd=repo_path,
                capture_output=True,
            )
            raise RuntimeError(
                f"Working tree was modified during analysis at '{repo_path}'. "
                f"Reset to SHA '{sha}'. Changes detected:\n{git_status.stdout}"
            )

        # Step 7: Validate and enrich result
        required_fields = [
            "repo", "sha", "role", "root_cause", "affected_component",
            "evidence", "confidence", "uncertainty", "recommended_next_action"
        ]
        for field in required_fields:
            if field not in result:
                raise RuntimeError(f"Missing required field in LLM response: {field}")

        # Ensure repo and sha match
        result["repo"] = repo_path
        result["sha"] = sha
        result["role"] = "root-cause-analyzer"

        # Clean up cloned repo if applicable
        if was_cloned:
            # Remove the temporary cloned repository
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)

        return result

    except json.JSONDecodeError as e:
        # Clean up cloned repo on error if applicable
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise RuntimeError(f"Invalid JSON response from LLM: {e}")
    except Exception as e:
        # Clean up cloned repo on any error
        if was_cloned:
            subprocess.run(["rm", "-rf", repo_path], capture_output=True)
        raise


def read_file_content(file_path: str) -> str:
    """Read content from a file path."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    return path.read_text(encoding="utf-8")


def print_terminal_summary(result: dict) -> None:
    """Print a human-readable summary to stderr."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("ROOT CAUSE ANALYSIS RESULT", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Repository: {result.get('repo', 'N/A')}", file=sys.stderr)
    print(f"SHA: {result.get('sha', 'N/A')}", file=sys.stderr)
    print(f"Role: {result.get('role', 'N/A')}", file=sys.stderr)
    print(f"Confidence: {result.get('confidence', 'N/A')}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print(f"ROOT CAUSE: {result.get('root_cause', 'N/A')}", file=sys.stderr)
    print(f"AFFECTED COMPONENT: {result.get('affected_component', 'N/A')}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print("EVIDENCE:", file=sys.stderr)
    for item in result.get("evidence", []):
        print(f"  - {item}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print(f"UNCERTAINTY: {result.get('uncertainty', 'None')}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)
    print(f"RECOMMENDED NEXT ACTION: {result.get('recommended_next_action', 'N/A')}", file=sys.stderr)
    print("=" * 60 + "\n", file=sys.stderr)


def main() -> None:
    """CLI entrypoint for rca_engine.py analyze."""
    parser = argparse.ArgumentParser(
        description="SAFI Root Cause Analysis Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rca_engine.py analyze --repo /path/to/repo --sha abc123 --evidence error.log
  python rca_engine.py analyze --repo . --sha HEAD --evidence evidence.txt --sow sow.md
  safi-rca analyze --repo /path/to/repo --sha abc123 --evidence error.log
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser("analyze", help="Run RCA analysis")
    analyze_parser.add_argument(
        "--repo", required=True, help="Path to the Git repository"
    )
    analyze_parser.add_argument(
        "--sha", required=True, help="Git commit SHA to analyze"
    )
    analyze_parser.add_argument(
        "--evidence", required=True, help="Path to failure evidence file"
    )
    analyze_parser.add_argument(
        "--sow", help="Optional path to Statement of Work (SOW) file"
    )

    args = parser.parse_args()

    if args.command == "analyze":
        try:
            # Read evidence file
            evidence = read_file_content(args.evidence)

            # Read SOW file if provided
            sow_content = ""
            if args.sow:
                sow_content = read_file_content(args.sow)

            # Run analysis
            result = run_rca_analysis(
                repo_path=args.repo,
                sha=args.sha,
                evidence=evidence,
                sow_content=sow_content,
            )

            # Print terminal summary to stderr
            print_terminal_summary(result)

            # Print JSON to stdout (for piping/parsing)
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()