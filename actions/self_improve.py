"""
self_improve.py — Vega self-improvement system.

Logs every tool call with timestamp.
Every Monday generates a weekly report:
  - Most used tools
  - Usage patterns by hour
  - Suggested shortcuts based on patterns
  - New capabilities Anas hasn't discovered yet
"""

from __future__ import annotations
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


USAGE_PATH  = get_base_dir() / "memory" / "tool_usage.json"
REPORT_PATH = get_base_dir() / "memory" / "weekly_report.json"

# Tools Anas might not know about
HIDDEN_GEMS = {
    "flight_finder":  "I can search Google Flights for you — just say 'find flights from Granada to Madrid'",
    "screen_process": "I can see your screen — say 'what's on my screen?' anytime",
    "dev_agent":      "I can build entire projects — say 'build me a React todo app'",
    "game_updater":   "I can update your Steam/Epic games automatically",
    "desktop_control":"I can change your wallpaper, organize your desktop files",
    "code_review":    "I can review your git commits — say 'review my last commit'",
    "ugr_summary":    "I can check your PRADO grades and deadlines",
    "job_tracker":    "I track your internship applications — say 'I applied to X'",
}


def _load_usage() -> list:
    try:
        if USAGE_PATH.exists():
            return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_usage(usage: list) -> None:
    try:
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Keep last 30 days only
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        usage  = [u for u in usage if u.get("time", "") > cutoff]
        USAGE_PATH.write_text(json.dumps(usage, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[SelfImprove] ⚠️ {e}")


def log_tool_call(tool_name: str) -> None:
    """Called by main.py every time a tool is dispatched."""
    usage = _load_usage()
    usage.append({
        "tool": tool_name,
        "time": datetime.now().isoformat(),
        "day":  datetime.now().strftime("%A"),
        "hour": datetime.now().hour,
    })
    _save_usage(usage)


def _should_generate_report() -> bool:
    """Generate on Mondays or if report is >7 days old."""
    today = date.today()
    try:
        if REPORT_PATH.exists():
            report = json.loads(REPORT_PATH.read_text())
            last   = date.fromisoformat(report.get("generated", "2000-01-01"))
            return (today - last).days >= 7
    except Exception:
        pass
    return today.weekday() == 0   # Monday


def generate_weekly_report(parameters: dict | None = None, player=None, speak=None) -> str:
    """Generate and return the weekly usage report."""
    usage = _load_usage()
    if not usage:
        return "No usage data yet. Use me for a week and I'll generate your first report!"

    # Last 7 days
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    week   = [u for u in usage if u.get("time", "") > cutoff]

    if not week:
        return "Not enough data from the past week to generate a report."

    # Tool frequency
    tool_counts = Counter(u["tool"] for u in week)
    top_tools   = tool_counts.most_common(5)

    # Peak usage hours
    hour_counts = Counter(u["hour"] for u in week)
    peak_hour   = hour_counts.most_common(1)[0][0] if hour_counts else 12
    peak_label  = f"{peak_hour:02d}:00–{peak_hour+1:02d}:00"

    # Busiest day
    day_counts  = Counter(u["day"] for u in week)
    busiest_day = day_counts.most_common(1)[0][0] if day_counts else "Monday"

    # Unused tools (hidden gems)
    used_tools  = set(tool_counts.keys())
    suggestions = [(t, tip) for t, tip in HIDDEN_GEMS.items() if t not in used_tools][:3]

    # Build report
    lines = [
        f"📊 VEGA WEEKLY REPORT — {date.today()}",
        f"\n🔧 Most used tools this week ({len(week)} total calls):",
    ]
    for tool, count in top_tools:
        lines.append(f"  • {tool}: {count}x")

    lines += [
        f"\n⏰ You use me most at {peak_label} on {busiest_day}s",
        f"\n💡 Features you haven't tried yet:",
    ]
    for tool, tip in suggestions:
        lines.append(f"  • {tip}")

    if not suggestions:
        lines.append("  You're using everything — power user! 💪")

    report_text = "\n".join(lines)

    # Save report
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps({
            "generated": str(date.today()),
            "text": report_text,
            "top_tools": dict(top_tools),
        }, indent=2))
    except Exception:
        pass

    return report_text


def check_and_deliver_report(speak_fn=None) -> str | None:
    """
    Called at startup — if it's Monday or report is overdue,
    generate and return the report so Vega can read it.
    """
    if _should_generate_report():
        report = generate_weekly_report()
        if speak_fn:
            speak_fn(f"Sir Anas, here is your weekly Vega report. {report}")
        return report
    return None
