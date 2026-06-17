"""
github_summary.py — GitHub activity summary for Vega.

Fetches Anas's recent commits, PRs, and repos from the GitHub API.
No auth token needed for public repos; optional token for private ones.
"""

from __future__ import annotations
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_github_token() -> str | None:
    try:
        path = get_base_dir() / "config" / "api_keys.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("github_token") or None
    except Exception:
        return None


def _headers() -> dict:
    token = _get_github_token()
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _get_username() -> str:
    """Try to get GitHub username from knowledge base, fallback to search."""
    try:
        kb = get_base_dir() / "memory" / "knowledge" / "anas_profile.txt"
        text = kb.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "github" in line.lower() and "/" in line:
                parts = line.split("/")
                return parts[-1].strip().split()[0]
    except Exception:
        pass
    return "anas-ai"   # placeholder — user sets this


def github_summary(parameters: dict | None = None, player=None, speak=None) -> str:
    """
    Fetches GitHub activity for the past week and returns a text summary.

    Parameters:
        action:   "week" (default) | "repos" | "prs" | "commits"
        username: GitHub username (optional, reads from knowledge base)
        days:     How many days to look back (default: 7)
    """
    if not _HAS_REQUESTS:
        return "The 'requests' library is required. Run: pip install requests"

    params   = parameters or {}
    action   = params.get("action", "week")
    days     = int(params.get("days", 7))
    username = params.get("username") or _get_username()
    since    = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z")

    if player:
        try: player.set_state("THINKING")
        except Exception: pass

    try:
        lines = [f"📊 GitHub activity for @{username} — last {days} days\n"]

        if action in ("week", "repos"):
            # Recent repos (updated in the period)
            r = requests.get(
                f"https://api.github.com/users/{username}/repos",
                headers=_headers(),
                params={"sort": "pushed", "per_page": 10},
                timeout=10
            )
            if r.status_code == 200:
                repos = r.json()
                recent = [
                    rp for rp in repos
                    if rp.get("pushed_at", "") >= since
                ]
                if recent:
                    lines.append("🗂 Active repos:")
                    for rp in recent[:5]:
                        pushed = rp["pushed_at"][:10]
                        lang   = rp.get("language") or "—"
                        lines.append(f"  • {rp['name']} ({lang}) — last push {pushed}")
                else:
                    lines.append("No repo activity in this period.")
            elif r.status_code == 404:
                return f"GitHub user '{username}' not found. Check the username in your knowledge base."

        if action in ("week", "commits"):
            # Recent commits via events API
            r = requests.get(
                f"https://api.github.com/users/{username}/events/public",
                headers=_headers(),
                params={"per_page": 100},
                timeout=10
            )
            if r.status_code == 200:
                events   = r.json()
                pushes   = [
                    e for e in events
                    if e.get("type") == "PushEvent"
                    and e.get("created_at", "") >= since
                ]
                commit_count = sum(len(e["payload"].get("commits", [])) for e in pushes)
                repo_names   = list({e["repo"]["name"].split("/")[-1] for e in pushes})

                lines.append(f"\n📝 Commits: {commit_count} across {len(pushes)} pushes")
                if repo_names:
                    lines.append(f"   In: {', '.join(repo_names[:5])}")

                # List last 5 commit messages
                recent_commits = []
                for e in pushes[:5]:
                    for c in e["payload"].get("commits", [])[:2]:
                        msg = c.get("message", "").split("\n")[0][:80]
                        recent_commits.append(f"  • {msg}")
                if recent_commits:
                    lines.append("\nRecent commits:")
                    lines.extend(recent_commits[:6])

        if action in ("week", "prs"):
            # PRs (search API)
            r = requests.get(
                "https://api.github.com/search/issues",
                headers=_headers(),
                params={
                    "q": f"author:{username} type:pr created:>{since[:10]}",
                    "per_page": 10,
                },
                timeout=10
            )
            if r.status_code == 200:
                prs = r.json().get("items", [])
                if prs:
                    lines.append(f"\n🔀 Pull Requests ({len(prs)}):")
                    for pr in prs[:5]:
                        state = "✅" if pr["state"] == "closed" else "🔄"
                        lines.append(f"  {state} {pr['title'][:70]}")

        result = "\n".join(lines)
        if speak:
            speak(result)
        return result

    except Exception as e:
        err = f"GitHub summary failed: {e}"
        print(f"[GitHub] ⚠️ {err}")
        return err
    finally:
        if player:
            try: player.set_state("LISTENING")
            except Exception: pass
