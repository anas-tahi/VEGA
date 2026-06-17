"""
ugr_prado.py — UGR PRADO portal scraper for Vega.

Logs into PRADO (Moodle) with Anas's credentials,
scrapes courses, upcoming deadlines, and recent announcements.
"""

from __future__ import annotations
import json
import sys
import time as _time
from datetime import datetime
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    _PW = True
except ImportError:
    _PW = False


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR     = get_base_dir()
CONFIG_PATH  = BASE_DIR / "config" / "api_keys.json"
CACHE_PATH   = BASE_DIR / "memory" / "ugr_cache.json"

PRADO_URL    = "https://prado.ugr.es"
LOGIN_URL    = "https://prado.ugr.es/moodle/login/index.php"
DASHBOARD_URL= "https://prado.ugr.es/moodle/my/"


def _get_credentials() -> tuple[str, str]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data.get("ugr_email", ""), data.get("ugr_password", "")
    except Exception:
        return "", ""


def _save_cache(data: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data["cached_at"] = datetime.now().isoformat()
        CACHE_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _load_cache() -> dict | None:
    try:
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            age_hours = (datetime.now() - cached_at).total_seconds() / 3600
            if age_hours < 3:   # cache valid for 3 hours
                return data
    except Exception:
        pass
    return None


def fetch_ugr_data(force_refresh: bool = False) -> dict:
    """
    Returns dict with keys: courses, deadlines, announcements.
    Uses cache if available and fresh.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached:
            return cached

    if not _PW:
        return {"error": "Playwright not installed", "courses": [], "deadlines": [], "announcements": []}

    email, password = _get_credentials()
    if not email or not password:
        return {"error": "UGR credentials not configured", "courses": [], "deadlines": [], "announcements": []}

    result = {"courses": [], "deadlines": [], "announcements": []}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx     = browser.new_context()
            page    = ctx.new_page()

            # Login
            page.goto(LOGIN_URL, timeout=20000, wait_until="domcontentloaded")
            _time.sleep(1)

            try:
                page.fill("#username", email, timeout=5000)
                page.fill("#password", password, timeout=5000)
                page.click("#loginbtn", timeout=5000)
                _time.sleep(3)
            except Exception as e:
                print(f"[UGR] Login form error: {e}")
                ctx.close(); browser.close()
                return result

            # Check if logged in
            current_url = page.url
            if "login" in current_url.lower():
                print("[UGR] ⚠️ Login failed — check credentials")
                ctx.close(); browser.close()
                result["error"] = "Login failed — check UGR credentials in config/api_keys.json"
                return result

            print("[UGR] ✅ Logged into PRADO")

            # Go to dashboard
            page.goto(DASHBOARD_URL, timeout=15000, wait_until="domcontentloaded")
            _time.sleep(2)

            # Scrape course names
            try:
                course_els = page.query_selector_all(".coursename, .course-name, [data-type='course'] .aalink")
                for el in course_els[:10]:
                    name = el.inner_text(timeout=1000).strip()
                    if name and len(name) > 2:
                        result["courses"].append(name)
            except Exception:
                pass

            # Scrape upcoming deadlines/events
            try:
                page.goto(f"{PRADO_URL}/moodle/calendar/view.php?view=upcoming", timeout=15000)
                _time.sleep(2)
                event_els = page.query_selector_all(".event, .calendar_event_course, [data-event-title]")
                for el in event_els[:10]:
                    try:
                        title = el.get_attribute("data-event-title") or el.inner_text(timeout=1000)
                        title = title.strip()[:100]
                        if title:
                            result["deadlines"].append(title)
                    except Exception:
                        pass
            except Exception:
                pass

            # Scrape recent announcements from dashboard
            try:
                page.goto(DASHBOARD_URL, timeout=15000)
                _time.sleep(1)
                ann_els = page.query_selector_all(".post-subject, .forumpost .subject, .message-subject")
                for el in ann_els[:5]:
                    txt = el.inner_text(timeout=1000).strip()
                    if txt:
                        result["announcements"].append(txt)
            except Exception:
                pass

            ctx.close()
            browser.close()

    except Exception as e:
        print(f"[UGR] ⚠️ Error: {e}")
        result["error"] = str(e)

    _save_cache(result)
    return result


def ugr_summary(parameters: dict | None = None, player=None, speak=None) -> str:
    """Tool entry point — called by main.py dispatcher."""
    action = (parameters or {}).get("action", "summary")
    force  = (parameters or {}).get("refresh", False)

    if player:
        try: player.set_state("THINKING")
        except Exception: pass

    data = fetch_ugr_data(force_refresh=force)

    if "error" in data and not data.get("courses"):
        return f"Could not access PRADO: {data['error']}"

    lines = ["Here's your UGR PRADO summary:"]

    if data.get("courses"):
        lines.append(f"\n📚 Courses ({len(data['courses'])}):")
        for c in data["courses"][:5]:
            lines.append(f"  • {c}")

    if data.get("deadlines"):
        lines.append(f"\n⏰ Upcoming deadlines:")
        for d in data["deadlines"][:5]:
            lines.append(f"  • {d}")
    else:
        lines.append("\n⏰ No upcoming deadlines found.")

    if data.get("announcements"):
        lines.append(f"\n📢 Recent announcements:")
        for a in data["announcements"][:3]:
            lines.append(f"  • {a}")

    if player:
        try: player.set_state("LISTENING")
        except Exception: pass

    return "\n".join(lines)
