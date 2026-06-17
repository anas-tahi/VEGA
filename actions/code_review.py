"""
code_review.py — Voice-triggered Git code review for Vega.

Say: "review my last commit" → reads git diff → summarizes with Gemini
Say: "review changes in main.py" → reviews specific file
"""

from __future__ import annotations
import subprocess
import sys
import json
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _run_git(args: list[str], cwd: str | None = None) -> tuple[str, str]:
    """Run a git command and return (stdout, stderr)."""
    try:
        r = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True,
            cwd=cwd, timeout=15
        )
        return r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return "", "Git is not installed or not in PATH"
    except subprocess.TimeoutExpired:
        return "", "Git command timed out"
    except Exception as e:
        return "", str(e)


def _find_git_repo(hint_path: str | None = None) -> str | None:
    """Find the nearest git repo — from hint path or common locations."""
    candidates = []
    if hint_path:
        candidates.append(hint_path)
    # Common developer locations
    home = Path.home()
    candidates += [
        str(home / "Desktop"),
        str(home / "Documents"),
        str(home / "Projects"),
        str(home / "dev"),
        str(home),
    ]
    for path in candidates:
        out, _ = _run_git(["rev-parse", "--show-toplevel"], cwd=path)
        if out:
            return out
    return None


def _get_diff(repo: str, file_path: str | None = None, commits: int = 1) -> str:
    if file_path:
        diff, err = _run_git(["diff", "HEAD", "--", file_path], cwd=repo)
        if not diff:
            diff, err = _run_git(["diff", f"HEAD~{commits}", "HEAD", "--", file_path], cwd=repo)
    else:
        diff, err = _run_git([f"diff", f"HEAD~{commits}", "HEAD"], cwd=repo)
        if not diff:
            diff, err = _run_git(["diff", "HEAD"], cwd=repo)

    return diff[:6000] if diff else ""   # cap at 6000 chars


def _get_last_commit_info(repo: str) -> str:
    msg, _ = _run_git(["log", "-1", "--pretty=%B %an %ad", "--date=short"], cwd=repo)
    return msg


def _summarize_with_gemini(diff: str, commit_info: str, api_key: str) -> str:
    """Call Gemini to summarize the diff."""
    try:
        import google.genai as genai
        client  = genai.Client(api_key=api_key)
        prompt  = (
            f"You are a senior code reviewer. "
            f"Review this git diff and give a concise summary suitable for reading aloud. "
            f"Cover: what changed, potential issues, quality assessment. "
            f"Keep it under 5 sentences.\n\n"
            f"Last commit: {commit_info}\n\n"
            f"Diff:\n{diff}"
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"Could not generate AI summary: {e}"


def code_review(parameters: dict | None = None, player=None, speak=None) -> str:
    """Tool entry point."""
    if player:
        try: player.set_state("THINKING")
        except Exception: pass

    p         = parameters or {}
    file_path = p.get("file_path")
    repo_hint = p.get("repo_path")
    commits   = int(p.get("commits", 1))

    # Find repo
    repo = _find_git_repo(repo_hint)
    if not repo:
        return "No git repository found. Make sure you're in a project folder."

    print(f"[CodeReview] 📁 Repo: {repo}")

    # Get commit info
    commit_info = _get_last_commit_info(repo)

    # Get diff
    diff = _get_diff(repo, file_path, commits)
    if not diff:
        return (
            f"No changes found in the last {commits} commit(s). "
            "The working tree might be clean or there's nothing to review."
        )

    # Load API key
    try:
        config = json.loads((get_base_dir() / "config" / "api_keys.json").read_text())
        api_key = config.get("gemini_api_key", "")
    except Exception:
        api_key = ""

    if not api_key:
        # Return raw diff summary without AI
        lines   = diff.split("\n")
        added   = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        return (
            f"Found {added} additions and {removed} deletions in the last commit.\n"
            f"Commit: {commit_info}\n"
            "Add your Gemini API key to config/api_keys.json for an AI summary."
        )

    summary = _summarize_with_gemini(diff, commit_info, api_key)

    if player:
        try: player.set_state("LISTENING")
        except Exception: pass

    return f"Code review for last commit:\n{summary}"
