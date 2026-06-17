"""
morning_checkin.py — Vega daily morning routine.

Opens Google Calendar in the browser, reads today's events via Playwright,
then returns a structured summary so the LLM can brief the user.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import re
import sys
import threading
import time
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Playwright import guard
# ---------------------------------------------------------------------------
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    _PW = True
except ImportError:
    _PW = False


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = get_base_dir()
_STATE_PATH  = _BASE / "memory" / "morning_state.json"


# ---------------------------------------------------------------------------
# State helpers — track whether we already did the check-in today
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        if _STATE_PATH.exists():
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def already_done_today() -> bool:
    """Returns True if the morning check-in was already completed today."""
    state = _load_state()
    return state.get("last_checkin") == str(date.today())


def mark_done_today() -> None:
    state = _load_state()
    state["last_checkin"] = str(date.today())
    _save_state(state)


# ---------------------------------------------------------------------------
# Calendar scraping
# ---------------------------------------------------------------------------

def _scrape_google_calendar() -> list[dict]:
    """
    Opens Google Calendar in a visible Chrome window (user already logged in),
    waits for today's events to load, and returns them as a list of dicts:
        [{"time": "09:00", "title": "Team standup"}, ...]
    Falls back to an empty list on any error.
    """
    if not _PW:
        return []

    events: list[dict] = []

    try:
        with sync_playwright() as pw:
            # Use real Chrome profile so user is already logged in
            import platform, os
            system = platform.system()
            if system == "Windows":
                profile_dir = os.path.expandvars(
                    r"%LOCALAPPDATA%\Google\Chrome\User Data"
                )
            elif system == "Darwin":
                profile_dir = os.path.expanduser(
                    "~/Library/Application Support/Google/Chrome"
                )
            else:
                profile_dir = os.path.expanduser("~/.config/google-chrome")

            ctx = None
            try:
                ctx = pw.chromium.launch_persistent_context(
                    profile_dir,
                    channel="chrome",
                    headless=False,
                    args=["--no-first-run", "--no-default-browser-check"],
                    timeout=15000,
                )
            except Exception as e:
                print(f"[Vega/Calendar] Chrome profile failed ({e}), trying plain Chromium")
                browser = pw.chromium.launch(headless=False)
                ctx = browser.new_context()

            try:
                page = ctx.new_page()
                page.goto(
                    "https://calendar.google.com/calendar/r/day",
                    timeout=20000,
                    wait_until="domcontentloaded"
                )

                # Wait for calendar to render — use page.wait_for_timeout correctly
                import time as _time
                _time.sleep(5)

                # Strategy 1: aria-label on event chips
                try:
                    event_els = page.query_selector_all(
                        '[data-eventid], [data-eventchip], [role="button"][data-eventid]'
                    )
                    for el in event_els[:20]:
                        try:
                            label = el.get_attribute("aria-label") or el.inner_text(timeout=1000)
                            label = label.strip()
                            if not label or len(label) < 3:
                                continue
                            time_match = re.search(
                                r"\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b", label
                            )
                            t = time_match.group(1) if time_match else ""
                            title = re.sub(
                                r"\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*[-–]?\s*", "", label
                            ).strip()
                            if title and len(title) > 2:
                                events.append({"time": t, "title": title})
                        except Exception:
                            continue
                except Exception:
                    pass

                # Strategy 2: grab all text from the day view column
                if not events:
                    try:
                        raw = page.inner_text("body") or ""
                        lines = [l.strip() for l in raw.splitlines() if l.strip()]
                        for line in lines:
                            if re.search(r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b", line, re.IGNORECASE):
                                time_match = re.search(
                                    r"(\d{1,2}:\d{2}\s*(?:AM|PM))", line, re.IGNORECASE
                                )
                                t = time_match.group(1) if time_match else ""
                                title = re.sub(
                                    r"\d{1,2}:\d{2}\s*(?:AM|PM)\s*[-–]?\s*",
                                    "", line, flags=re.IGNORECASE
                                ).strip()
                                if title and len(title) > 3:
                                    events.append({"time": t, "title": title})
                    except Exception:
                        pass

            finally:
                # Always close cleanly
                try:
                    ctx.close()
                except Exception:
                    pass

    except Exception as e:
        print(f"[Vega/Calendar] ⚠️ {e}")

    # Deduplicate
    seen, unique = set(), []
    for ev in events:
        key = ev["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return unique[:15]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def morning_checkin(parameters: dict | None = None, player=None, speak=None) -> str:
    """
    Called by the tool dispatcher.
    Returns a text summary for the LLM to read out.
    """
    if player:
        try:
            player.set_state("THINKING")
        except Exception:
            pass

    events = _scrape_google_calendar()
    mark_done_today()

    today = date.today().strftime("%A, %B %d")

    if events:
        lines = []
        for ev in events:
            if ev["time"]:
                lines.append(f"  • {ev['time']} — {ev['title']}")
            else:
                lines.append(f"  • {ev['title']}")
        calendar_summary = f"Today is {today}. Here are your events:\n" + "\n".join(lines)
    else:
        calendar_summary = (
            f"Today is {today}. I couldn't find any events on your Google Calendar, "
            "or the calendar may still be loading. You might want to check it manually."
        )

    if player:
        try:
            player.set_state("LISTENING")
        except Exception:
            pass

    return calendar_summary
