"""
job_tracker.py — Prácticas / internship tracker for Vega.

Voice commands:
  "I applied to Accenture in Sevilla"  → logs application
  "What's the status of my applications?" → lists all
  "Search for new internships"          → searches Indeed/Infojobs
  "Follow up on Accenture"             → marks as followed-up
"""

from __future__ import annotations
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from duckduckgo_search import DDGS
    _DDG = True
except ImportError:
    _DDG = False


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


TRACKER_PATH = get_base_dir() / "memory" / "job_tracker.json"
FOLLOW_UP_DAYS = 7   # remind to follow up after 7 days


def _load() -> list:
    try:
        if TRACKER_PATH.exists():
            return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save(apps: list) -> None:
    try:
        TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
        TRACKER_PATH.write_text(json.dumps(apps, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[JobTracker] ⚠️ save failed: {e}")


def _log_application(company: str, location: str = "", role: str = "Web Developer Intern") -> str:
    apps = _load()
    # Check for duplicate
    for app in apps:
        if app["company"].lower() == company.lower():
            return f"You already have an application logged for {company} (status: {app['status']})."
    entry = {
        "company":    company,
        "role":       role,
        "location":   location,
        "applied_on": str(date.today()),
        "status":     "applied",
        "notes":      "",
        "follow_up":  str(date.today() + timedelta(days=FOLLOW_UP_DAYS)),
    }
    apps.append(entry)
    _save(apps)
    return f"✅ Logged application to {company} ({role}) in {location or 'unknown location'}. I'll remind you to follow up in {FOLLOW_UP_DAYS} days."


def _list_applications() -> str:
    apps = _load()
    if not apps:
        return "No applications logged yet. Tell me when you apply somewhere and I'll track it."

    today = date.today()
    lines = [f"📋 You have {len(apps)} application(s) logged:\n"]
    overdue = []

    for app in sorted(apps, key=lambda x: x["applied_on"], reverse=True):
        status_emoji = {
            "applied":    "📤",
            "followed_up":"📧",
            "interview":  "🎯",
            "rejected":   "❌",
            "offer":      "🎉",
        }.get(app["status"], "•")

        follow_date = date.fromisoformat(app["follow_up"])
        overdue_tag = " ⚠️ FOLLOW UP NOW" if follow_date <= today and app["status"] == "applied" else ""
        if overdue_tag:
            overdue.append(app["company"])

        lines.append(
            f"{status_emoji} {app['company']} — {app['role']}"
            f"\n   📍 {app.get('location','?')}  |  Applied: {app['applied_on']}"
            f"\n   Status: {app['status']}{overdue_tag}"
        )

    if overdue:
        lines.append(f"\n⚠️ Follow up needed: {', '.join(overdue)}")

    return "\n".join(lines)


def _update_status(company: str, status: str) -> str:
    apps = _load()
    for app in apps:
        if company.lower() in app["company"].lower():
            app["status"] = status
            if status == "followed_up":
                app["follow_up"] = str(date.today() + timedelta(days=FOLLOW_UP_DAYS))
            _save(apps)
            return f"✅ Updated {app['company']} status to '{status}'."
    return f"No application found for '{company}'. Did you log it?"


def _search_listings(location: str = "Granada") -> str:
    if not _DDG:
        return "DuckDuckGo search not available. Install: pip install duckduckgo-search"

    queries = [
        f"prácticas desarrollador web {location} 2025",
        f"internship web developer {location} Spain",
        f"becas informática {location} empresa",
    ]

    results = []
    try:
        with DDGS() as ddg:
            for q in queries[:2]:
                hits = list(ddg.text(q, max_results=3))
                for h in hits:
                    title = h.get("title", "")
                    url   = h.get("href", "")
                    if title and url:
                        results.append(f"• {title}\n  {url}")
    except Exception as e:
        return f"Search failed: {e}"

    if not results:
        return "No listings found right now. Try again later."

    return f"🔍 Found {len(results)} internship listings:\n\n" + "\n\n".join(results[:6])


def _check_follow_ups() -> str:
    """Called at startup — check if any applications need follow-up today."""
    apps = _load()
    today = date.today()
    due = [a for a in apps if a["status"] == "applied"
           and date.fromisoformat(a["follow_up"]) <= today]
    if not due:
        return ""
    companies = ", ".join(a["company"] for a in due)
    return f"⚠️ Follow-up reminder: {companies} — it's been {FOLLOW_UP_DAYS}+ days since you applied."


def job_tracker(parameters: dict | None = None, player=None, speak=None) -> str:
    """Main tool entry point."""
    if player:
        try: player.set_state("THINKING")
        except Exception: pass

    p      = parameters or {}
    action = p.get("action", "list")

    if action == "log":
        result = _log_application(
            company  = p.get("company", "Unknown"),
            location = p.get("location", ""),
            role     = p.get("role", "Web Developer Intern"),
        )
    elif action == "list":
        result = _list_applications()
    elif action == "update":
        result = _update_status(p.get("company", ""), p.get("status", "followed_up"))
    elif action == "search":
        result = _search_listings(p.get("location", "Granada Sevilla Malaga"))
    elif action == "follow_ups":
        result = _check_follow_ups() or "No follow-ups due today."
    else:
        result = _list_applications()

    if player:
        try: player.set_state("LISTENING")
        except Exception: pass

    return result
