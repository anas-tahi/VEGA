"""
proactive_alerts.py — Background proactive alert system for Vega.

Runs checks on a schedule and speaks up without being asked:
- Job application follow-up reminders
- Weather warnings before typical commute hours
- Upcoming deadlines from UGR PRADO (if cached)
- Weekly report delivery on Mondays
- Morning calendar summary (if user hasn't disabled it)

All checks are non-blocking, run in daemon threads.
"""

from __future__ import annotations
import json
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR       = get_base_dir()
ALERTS_STATE   = BASE_DIR / "memory" / "alerts_state.json"

# How often to run each check (seconds)
CHECK_INTERVAL = 60 * 15   # every 15 minutes


def _load_state() -> dict:
    try:
        if ALERTS_STATE.exists():
            return json.loads(ALERTS_STATE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        ALERTS_STATE.parent.mkdir(parents=True, exist_ok=True)
        ALERTS_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass


def _already_alerted_today(key: str) -> bool:
    state = _load_state()
    return state.get(key) == str(date.today())


def _mark_alerted(key: str) -> None:
    state = _load_state()
    state[key] = str(date.today())
    _save_state(state)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_job_followups(speak):
    """Alert if any job application is overdue for follow-up."""
    if _already_alerted_today("job_followup"):
        return
    try:
        from actions.job_tracker import _check_follow_ups
        msg = _check_follow_ups()
        if msg:
            speak(f"Sir Anas, job tracker alert: {msg}")
            _mark_alerted("job_followup")
    except Exception as e:
        print(f"[Alerts] ⚠️ job_followup check failed: {e}")


def _check_morning_weather(speak):
    """At 8 AM, speak today's weather if not already done."""
    hour = datetime.now().hour
    if hour != 8 or _already_alerted_today("morning_weather"):
        return
    try:
        from actions.weather_report import weather_action
        result = weather_action(parameters={"city": "Granada"}, player=None)
        if result:
            speak(f"Good morning weather update, Sir Anas. {result}")
            _mark_alerted("morning_weather")
    except Exception as e:
        print(f"[Alerts] ⚠️ morning_weather check failed: {e}")


def _check_weekly_report(speak):
    """On Monday mornings, deliver the weekly usage report."""
    now = datetime.now()
    if now.weekday() != 0 or now.hour < 9 or _already_alerted_today("weekly_report"):
        return
    try:
        from actions.self_improve import _should_generate_report, generate_weekly_report
        if _should_generate_report():
            report = generate_weekly_report()
            speak(f"Sir Anas, here is your weekly Vega usage report. {report}")
            _mark_alerted("weekly_report")
    except Exception as e:
        print(f"[Alerts] ⚠️ weekly_report check failed: {e}")


def _check_prado_deadlines(speak):
    """Once a day in the morning, warn about upcoming PRADO deadlines."""
    hour = datetime.now().hour
    if hour < 9 or hour > 10 or _already_alerted_today("prado_deadlines"):
        return
    try:
        cached = BASE_DIR / "memory" / "prado_cache.json"
        if not cached.exists():
            return
        data = json.loads(cached.read_text(encoding="utf-8"))
        deadlines = data.get("deadlines", [])
        tomorrow  = (date.today() + timedelta(days=1)).isoformat()
        upcoming  = [d for d in deadlines if d.get("date", "") == tomorrow]
        if upcoming:
            items = ", ".join(d.get("title", "task") for d in upcoming)
            speak(f"Heads up Sir Anas, you have PRADO deadlines tomorrow: {items}")
            _mark_alerted("prado_deadlines")
    except Exception as e:
        print(f"[Alerts] ⚠️ prado_deadlines check failed: {e}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

class ProactiveAlertSystem:
    """Background daemon that runs periodic checks and speaks proactively."""

    def __init__(self, speak_fn):
        self._speak = speak_fn
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="VegaAlerts"
        )
        self._thread.start()
        print("[Alerts] ✅ Proactive alert system started")

    def stop(self) -> None:
        self._running = False
        print("[Alerts] 🔴 Proactive alert system stopped")

    def _loop(self) -> None:
        # Wait a minute after startup before first check
        time.sleep(60)
        while self._running:
            try:
                self._run_all_checks()
            except Exception as e:
                print(f"[Alerts] ⚠️ Check cycle error: {e}")
            time.sleep(CHECK_INTERVAL)

    def _run_all_checks(self) -> None:
        checks = [
            _check_job_followups,
            _check_morning_weather,
            _check_weekly_report,
            _check_prado_deadlines,
        ]
        for check in checks:
            try:
                check(self._speak)
                time.sleep(2)   # small gap between alerts
            except Exception as e:
                print(f"[Alerts] ⚠️ {check.__name__}: {e}")


_alert_system: ProactiveAlertSystem | None = None


def start_alerts(speak_fn) -> None:
    """Call this once from main.py after the session is established."""
    global _alert_system
    if _alert_system is None:
        _alert_system = ProactiveAlertSystem(speak_fn)
        _alert_system.start()


def stop_alerts() -> None:
    global _alert_system
    if _alert_system:
        _alert_system.stop()
        _alert_system = None
