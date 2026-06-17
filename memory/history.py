"""
history.py — Full persistent conversation memory for Vega.

Saves every turn (user + assistant) to memory/history.json.
Injects the last 3 sessions into the system prompt at startup.
"""

from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


HISTORY_PATH = get_base_dir() / "memory" / "history.json"
MAX_SESSIONS = 10      # keep last 10 sessions on disk
INJECT_SESSIONS = 3    # inject last 3 into prompt


def _load() -> list:
    try:
        if HISTORY_PATH.exists():
            return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save(sessions: list) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps(sessions[-MAX_SESSIONS:], indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[History] ⚠️ save failed: {e}")


# In-memory current session buffer
_current_session: list[dict] = []
_session_start: str = datetime.now().isoformat()


def log_turn(role: str, text: str) -> None:
    """Log a conversation turn. role = 'user' or 'assistant'."""
    if not text or not text.strip():
        return
    _current_session.append({
        "role": role,
        "text": text.strip(),
        "time": datetime.now().strftime("%H:%M"),
    })
    # Auto-save every 5 turns
    if len(_current_session) % 5 == 0:
        flush()


def flush() -> None:
    """Save current session to disk."""
    if not _current_session:
        return
    sessions = _load()
    sessions.append({
        "date": _session_start,
        "turns": list(_current_session),
    })
    _save(sessions)


def get_recent_context(n: int = INJECT_SESSIONS) -> str:
    """
    Returns the last n sessions formatted for injection into the system prompt.
    """
    sessions = _load()
    if not sessions:
        return ""

    recent = sessions[-n:]
    lines  = ["[CONVERSATION HISTORY — last sessions]\n"]

    for sess in recent:
        date = sess.get("date", "")[:10]
        lines.append(f"── Session {date} ──")
        for turn in sess.get("turns", [])[-20:]:  # max 20 turns per session
            role = "Sir Anas" if turn["role"] == "user" else "Vega"
            lines.append(f"{role}: {turn['text']}")
        lines.append("")

    return "\n".join(lines) + "\n"
