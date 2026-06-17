import asyncio
import re
import threading
import json
import sys
import traceback
from pathlib import Path

import sounddevice as sd
from google import genai
from google.genai import types
from ui import VegaUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)
from memory.rag import retrieve as _rag_retrieve


def _build_rag_context(query: str = "") -> str:
    """Pull relevant knowledge and format for system prompt injection."""
    return _rag_retrieve(query=query, max_chars=2000)

from actions.file_processor    import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.ugr_prado         import ugr_summary
from actions.job_tracker       import job_tracker, _check_follow_ups
from actions.code_review       import code_review
from actions.github_summary    import github_summary
from actions.self_improve      import log_tool_call, check_and_deliver_report, generate_weekly_report
from memory.history            import log_turn, flush as flush_history, get_recent_context
from actions.proactive_alerts  import start_alerts, stop_alerts



def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"

LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    key = data.get("gemini_api_key", "")
    if not key or key == "YOUR_GEMINI_API_KEY_HERE":
        raise ValueError(
            "No Gemini API key found.\n"
            "Please open config/api_keys.json and paste your key."
        )
    return key



def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are Vega, a sharp bilingual (English/Spanish) personal AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Respond in the same language the user speaks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)


def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _pick_input_device():
    """
    Dynamically finds the best available microphone input device.
    Prefers devices with 'microphone' or 'mic' in their name.
    Falls back to the first available input device.
    """
    try:
        devices = sd.query_devices()
        # First pass: prefer devices with 'mic' in name
        for idx, dev in enumerate(devices):
            max_in = int(dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0))
            name = (dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")).lower()
            if max_in > 0 and ("mic" in name or "microphone" in name):
                print(f"[VEGA] 🎤 Preferred mic device #{idx}: {name}")
                return idx

        # Second pass: any working input device
        for idx, dev in enumerate(devices):
            max_in = int(dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0))
            if max_in > 0:
                name = dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")
                print(f"[VEGA] 🎤 Using input device #{idx}: {name}")
                return idx

    except Exception as exc:
        print(f"[VEGA] ⚠️ Mic device scan failed: {exc}")
    return None


# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | brave"},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_vega",
        "description": (
            "Shuts down VEGA completely. "
            "ONLY call this when the user EXPLICITLY says one of: "
            "'shut down', 'close yourself', 'exit', 'apagarte', 'ciérrate', 'adiós cierra'. "
            "Do NOT call this for: greetings, silence, unclear audio, background noise, "
            "end of morning checkin, or any ambiguous phrase. "
            "If unsure — do NOT call this tool."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "file_processor",
        "description": (
            "Processes any file that the user has uploaded or dropped onto the interface. "
            "Use this when the user refers to an uploaded file and wants an action on it. "
            "Supports: images, PDFs, Word docs, CSV/Excel, JSON, code files, audio, video, archives, presentations."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path":   {"type": "STRING", "description": "Full path to the uploaded file."},
                "action":      {"type": "STRING", "description": "describe | summarize | extract_text | analyze | fix | run | transcribe | convert | info | etc."},
                "instruction": {"type": "STRING", "description": "Free-form instruction if action doesn't cover it."},
                "format":      {"type": "STRING", "description": "Target format for conversion."},
                "width":       {"type": "INTEGER"},
                "height":      {"type": "INTEGER"},
                "scale":       {"type": "NUMBER"},
                "quality":     {"type": "INTEGER"},
                "start":       {"type": "STRING"},
                "end":         {"type": "STRING"},
                "timestamp":   {"type": "STRING"},
                "column":      {"type": "STRING"},
                "value":       {"type": "STRING"},
                "condition":   {"type": "STRING"},
                "ascending":   {"type": "BOOLEAN"},
                "save":        {"type": "BOOLEAN"},
                "destination": {"type": "STRING"},
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity | preferences | projects | relationships | wishes | notes"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key"},
                "value": {"type": "STRING", "description": "Concise value in English"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "ugr_summary",
        "description": (
            "Checks the UGR PRADO student portal for Sir Anas. "
            "Returns courses, upcoming assignment deadlines, and recent announcements. "
            "Call when asked about university, PRADO, grades, deadlines, or assignments."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":  {"type": "STRING", "description": "summary (default) | deadlines | courses | announcements"},
                "refresh": {"type": "BOOLEAN", "description": "Force refresh ignoring cache"},
            },
            "required": []
        }
    },
    {
        "name": "job_tracker",
        "description": (
            "Tracks internship/prácticas applications for Sir Anas. "
            "Use for: logging a new application, listing all applications, "
            "updating status, searching for new listings, checking follow-ups. "
            "Examples: 'I applied to Accenture in Sevilla', 'what are my applications', "
            "'search for internships in Granada', 'I got an interview at X'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING", "description": "log | list | update | search | follow_ups"},
                "company":  {"type": "STRING", "description": "Company name"},
                "role":     {"type": "STRING", "description": "Job title (default: Web Developer Intern)"},
                "location": {"type": "STRING", "description": "City or region"},
                "status":   {"type": "STRING", "description": "applied | followed_up | interview | rejected | offer"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_review",
        "description": (
            "Reviews the last git commit or recent code changes. "
            "Call when user says 'review my last commit', 'what did I change', "
            "'review my code', 'check my git diff'. "
            "Returns an AI-powered summary of what changed and potential issues."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path":  {"type": "STRING", "description": "Specific file to review (optional)"},
                "repo_path":  {"type": "STRING", "description": "Path to git repo (optional, auto-detected)"},
                "commits":    {"type": "INTEGER", "description": "Number of commits to look back (default: 1)"},
            },
            "required": []
        }
    },
    {
        "name": "weekly_report",
        "description": (
            "Generates a weekly self-improvement report showing which tools were used most, "
            "peak usage hours, and features Anas hasn't tried yet. "
            "Call when user asks 'how am I using you', 'give me a weekly report', "
            "'what tools do I use most'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "github_summary",
        "description": (
            "Shows Sir Anas's recent GitHub activity: commits, repos, and pull requests. "
            "Call when asked 'what did I commit this week', 'show my GitHub activity', "
            "'what repos am I working on', 'my commits'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":   {"type": "STRING", "description": "week (default) | repos | commits | prs"},
                "days":     {"type": "INTEGER", "description": "How many days to look back (default: 7)"},
                "username": {"type": "STRING",  "description": "GitHub username (optional, auto-detected)"},
            },
            "required": []
        }
    },
]

# ---------------------------------------------------------------------------
# Tool dispatch map — replaces the old if-elif chain
# ---------------------------------------------------------------------------

def _make_dispatch(ui):
    """Returns a dict mapping tool name → async-compatible callable."""
    loop = asyncio.get_event_loop

    async def _run(fn, *args, **kwargs):
        return await asyncio.get_event_loop().run_in_executor(None, lambda: fn(*args, **kwargs))

    return {
        "open_app":         lambda args: open_app(parameters=args, response=None, player=ui),
        "web_search":       lambda args: web_search_action(parameters=args, player=ui),
        "weather_report":   lambda args: weather_action(parameters=args, player=ui),
        "send_message":     lambda args: send_message(parameters=args, response=None, player=ui, session_memory=None),
        "reminder":         lambda args: reminder(parameters=args, response=None, player=ui),
        "youtube_video":    lambda args: youtube_video(parameters=args, response=None, player=ui),
        "computer_settings":lambda args: computer_settings(parameters=args, response=None, player=ui),
        "browser_control":  lambda args: browser_control(parameters=args, player=ui),
        "file_controller":  lambda args: file_controller(parameters=args, player=ui),
        "desktop_control":  lambda args: desktop_control(parameters=args, player=ui),
        "code_helper":      lambda args, speak=None: code_helper(parameters=args, player=ui, speak=speak),
        "dev_agent":        lambda args, speak=None: dev_agent(parameters=args, player=ui, speak=speak),
        "computer_control": lambda args: computer_control(parameters=args, player=ui),
        "game_updater":     lambda args, speak=None: game_updater(parameters=args, player=ui, speak=speak),
        "flight_finder":    lambda args: flight_finder(parameters=args, player=ui),
        "morning_checkin":  lambda args: None,  # deprecated
    }


# ---------------------------------------------------------------------------
# Main session class
# ---------------------------------------------------------------------------

class VegaLive:

    def __init__(self, ui):
        self.ui              = ui
        self.session         = None
        self.audio_in_queue  = None
        self.out_queue       = None
        self._loop           = None
        self._is_speaking    = False
        self._speaking_lock  = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"There was an error with {tool_name}. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        hour     = now.hour
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")

        # Time-based greeting instruction
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        greeting_ctx = (
            f"[SESSION START — DO THIS ONCE IMMEDIATELY]\n"
            f"The moment the session begins, say EXACTLY:\n"
            f"\"{greeting}, Sir Anas.\"\n"
            f"ONE short sentence. Then go completely SILENT and wait for him to speak first.\n"
            f"Do NOT ask how he slept. Do NOT open the calendar. Do NOT mention anything.\n"
            f"Just greet and wait.\n\n"
        )

        # RAG — inject relevant knowledge into context
        rag_ctx = _build_rag_context()

        # Conversation history — last 3 sessions
        history_ctx = get_recent_context(3)

        # Follow-up reminders for job applications
        try:
            follow_up = _check_follow_ups()
            follow_ctx = (
                f"[JOB TRACKER ALERT]\n{follow_up}\n"
                f"Mention this to Sir Anas naturally during the session.\n\n"
            ) if follow_up else ""
        except Exception:
            follow_ctx = ""

        # Weekly report — deliver silently at startup if due
        try:
            from actions.self_improve import _should_generate_report
            weekly_ctx = ""
            if _should_generate_report():
                from actions.self_improve import generate_weekly_report
                report = generate_weekly_report()
                weekly_ctx = (
                    f"[WEEKLY REPORT — deliver this early in the session]\n"
                    f"{report}\n\n"
                )
        except Exception:
            weekly_ctx = ""

        parts = [time_ctx, greeting_ctx]
        if follow_ctx:
            parts.append(follow_ctx)
        if weekly_ctx:
            parts.append(weekly_ctx)
        if history_ctx:
            parts.append(history_ctx)
        if rag_ctx:
            parts.append(rag_ctx)
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
            # Disable extended thinking for faster first-word latency
            generation_config=types.GenerationConfig(
                temperature=0.7,
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[VEGA] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        result = "Done."

        try:
            # --- Memory ---
            if name == "save_memory":
                category = args.get("category", "notes")
                key      = args.get("key", "")
                value    = args.get("value", "")
                if key and value:
                    update_memory({category: {key: {"value": value}}})
                    print(f"[Memory] 💾 {category}/{key} = {value}")
                if not self.ui.muted:
                    self.ui.set_state("LISTENING")
                return types.FunctionResponse(
                    id=fc.id, name=name,
                    response={"result": "ok", "silent": True}
                )

            # --- Shutdown ---
            elif name == "shutdown_vega":
                self.ui.write_log("SYS: Shutdown requested.")
                try:
                    flush_history()
                except Exception:
                    pass
                self.speak("Goodbye, Sir Anas. VEGA signing off.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()
                return types.FunctionResponse(
                    id=fc.id, name=name, response={"result": "shutting down"}
                )

            # --- Screen (runs in its own thread, speaks directly) ---
            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated."

            # --- Agent task ---
            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            # --- File processor (needs ui.current_file) ---
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            # --- Tools that need speak callback ---
            elif name in ("code_helper", "dev_agent", "game_updater"):
                dispatch = {
                    "code_helper":  lambda: code_helper(parameters=args, player=self.ui, speak=self.speak),
                    "dev_agent":    lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak),
                    "game_updater": lambda: game_updater(parameters=args, player=self.ui, speak=self.speak),
                }
                r = await asyncio.get_event_loop().run_in_executor(None, dispatch[name])
                result = r or "Done."

            # --- All other tools (simple dispatch) ---
            else:
                simple_map = {
                    "open_app":          lambda: open_app(parameters=args, response=None, player=self.ui),
                    "web_search":        lambda: web_search_action(parameters=args, player=self.ui),
                    "weather_report":    lambda: weather_action(parameters=args, player=self.ui),
                    "send_message":      lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None),
                    "reminder":          lambda: reminder(parameters=args, response=None, player=self.ui),
                    "youtube_video":     lambda: youtube_video(parameters=args, response=None, player=self.ui),
                    "computer_settings": lambda: computer_settings(parameters=args, response=None, player=self.ui),
                    "browser_control":   lambda: browser_control(parameters=args, player=self.ui),
                    "file_controller":   lambda: file_controller(parameters=args, player=self.ui),
                    "desktop_control":   lambda: desktop_control(parameters=args, player=self.ui),
                    "computer_control":  lambda: computer_control(parameters=args, player=self.ui),
                    "flight_finder":     lambda: flight_finder(parameters=args, player=self.ui),
                    "ugr_summary":       lambda: ugr_summary(parameters=args, player=self.ui),
                    "job_tracker":       lambda: job_tracker(parameters=args, player=self.ui, speak=self.speak),
                    "code_review":       lambda: code_review(parameters=args, player=self.ui, speak=self.speak),
                    "weekly_report":     lambda: generate_weekly_report(parameters=args, player=self.ui),
                    "github_summary":    lambda: github_summary(parameters=args, player=self.ui, speak=self.speak),
                }
                if name in simple_map:
                    r = await asyncio.get_event_loop().run_in_executor(None, simple_map[name])
                    result = r or "Done."
                else:
                    result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        # Log tool usage for self-improvement
        try:
            log_tool_call(name)
        except Exception:
            pass

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[VEGA] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(audio=msg)

    async def _listen_audio(self):
        global _CONFIRMED_MIC_DEVICE
        print("[VEGA] 🎤 Mic started")
        input_device = _pick_input_device()
        if input_device is None:
            print("[VEGA] ❌ No mic input device found")
            self.ui.write_log("ERR: No microphone found.")
            return
        print(f"[VEGA] 🎤 Using device #{input_device}")

        # Use the device's native sample rate to avoid silent capture
        try:
            dev_info = sd.query_devices(input_device)
            native_sr = int(dev_info.get("default_samplerate", 16000) if isinstance(dev_info, dict) else getattr(dev_info, "default_samplerate", 16000))
        except Exception:
            native_sr = 16000
        print(f"[VEGA] 🎤 Native sample rate: {native_sr}Hz")

        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if self.ui.muted:
                return
            try:
                import numpy as np
                # Resample to 16000 if needed
                if native_sr != SEND_SAMPLE_RATE:
                    ratio      = SEND_SAMPLE_RATE / native_sr
                    target_len = max(1, int(len(indata) * ratio))
                    indices    = np.round(np.linspace(0, len(indata) - 1, target_len)).astype(int)
                    data       = indata[indices].tobytes()
                else:
                    data = indata.tobytes()
                if not data:
                    return
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"data": data, "mime_type": "audio/pcm"}
                )
            except Exception as exc:
                print(f"[VEGA] ⚠️ Mic callback: {exc}")

        try:
            with sd.InputStream(
                samplerate=native_sr,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=input_device,
                callback=callback,
            ):
                print("[VEGA] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[VEGA] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[VEGA] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    # Fix 2: explicitly skip thought/text-only parts so they
                    # don't consume the iterator or confuse the audio pipeline
                    if hasattr(response, "type") and response.type in ("thought", "text"):
                        continue

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        # Skip model thought blocks silently
                        if hasattr(sc, "model_turn") and sc.model_turn:
                            for part in (sc.model_turn.parts or []):
                                if hasattr(part, "thought") and part.thought:
                                    continue  # discard thought tokens

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                print(f"[VEGA] 👤 heard: {txt}")
                                try:
                                    log_turn("user", txt)
                                except Exception:
                                    pass

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Vega: {full_out}")
                                try:
                                    log_turn("assistant", full_out)
                                except Exception:
                                    pass
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[VEGA] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[VEGA] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[VEGA] 🔊 Play started")
        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[VEGA] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        while True:
            try:
                print("[VEGA] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self.session         = session
                    self._loop           = asyncio.get_event_loop()
                    self.audio_in_queue  = asyncio.Queue()
                    self.out_queue       = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()

                    print("[VEGA] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: VEGA online.")
                    # Start proactive alert background system
                    start_alerts(self.speak)

                    tasks = [
                        asyncio.create_task(self._send_realtime()),
                        asyncio.create_task(self._listen_audio()),
                        asyncio.create_task(self._receive_audio()),
                        asyncio.create_task(self._play_audio()),
                    ]
                    try:
                        await asyncio.gather(*tasks)
                    except Exception as exc:
                        print(f"[VEGA] ⚠️ Session error: {exc}")
                        traceback.print_exc()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                print(f"[VEGA] ⚠️ {e}")
                traceback.print_exc()

            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[VEGA] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)


def _request_mic_permission() -> int | None:
    """
    Shows a Windows dialog asking for mic permission,
    tests each input device, and returns the first working device index.
    Returns None if no device works.
    """
    import tkinter as tk
    from tkinter import messagebox

    # Trigger Windows mic permission prompt by briefly opening a stream
    root = tk.Tk()
    root.withdraw()

    messagebox.showinfo(
        "Vega — Microphone Access",
        "Vega needs access to your microphone for voice interaction.\n\n"
        "Click OK to allow microphone access, then speak when prompted."
    )

    devices = sd.query_devices()
    working_device = None

    for idx, dev in enumerate(devices):
        max_in = int(dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0))
        if max_in == 0:
            continue
        sr = float(dev.get("default_samplerate", 44100) if isinstance(dev, dict) else getattr(dev, "default_samplerate", 44100))
        name = dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")
        try:
            import numpy as np
            rec = sd.rec(int(0.5 * sr), samplerate=int(sr), channels=1, dtype="int16", device=idx)
            sd.wait()
            rms = int(np.sqrt(np.mean(rec.astype(np.float32) ** 2)))
            print(f"[VEGA] 🎤 Device #{idx} ({name}): RMS={rms}")
            if rms > 20 and working_device is None:
                working_device = idx
                print(f"[VEGA] ✅ Selected device #{idx}: {name}")
        except Exception as e:
            print(f"[VEGA] ⚠️ Device #{idx} failed: {e}")

    if working_device is not None:
        messagebox.showinfo(
            "Vega — Microphone Ready",
            f"✅ Microphone is working!\n\nVega will now start.\nSpeak naturally after it connects."
        )
    else:
        messagebox.showwarning(
            "Vega — Microphone Issue",
            "⚠️ Could not detect audio from your microphone.\n\n"
            "Please check:\n"
            "• Windows Settings → Privacy → Microphone → Allow\n"
            "• Your mic is not muted\n"
            "• No other app is using the mic exclusively\n\n"
            "Vega will start anyway — you can use text input."
        )

    root.destroy()
    return working_device


# Global to store the confirmed working device index
_CONFIRMED_MIC_DEVICE: int | None = None


def _pick_input_device():
    global _CONFIRMED_MIC_DEVICE
    if _CONFIRMED_MIC_DEVICE is not None:
        return _CONFIRMED_MIC_DEVICE
    # Fallback: prefer 'mic' in name, then any input device
    try:
        devices = sd.query_devices()
        for idx, dev in enumerate(devices):
            max_in = int(dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0))
            name = (dev.get("name", "") if isinstance(dev, dict) else getattr(dev, "name", "")).lower()
            if max_in > 0 and "mic" in name:
                return idx
        for idx, dev in enumerate(devices):
            max_in = int(dev.get("max_input_channels", 0) if isinstance(dev, dict) else getattr(dev, "max_input_channels", 0))
            if max_in > 0:
                return idx
    except Exception:
        pass
    return None


def main():
    global _CONFIRMED_MIC_DEVICE

    # Step 1: request mic permission and find working device BEFORE UI starts
    print("[VEGA] 🎤 Requesting microphone permission...")
    _CONFIRMED_MIC_DEVICE = _request_mic_permission()
    print(f"[VEGA] 🎤 Confirmed mic device: #{_CONFIRMED_MIC_DEVICE}")

    # Step 2: launch UI
    ui = VegaUI("face.png")

    def runner():
        ui.wait_for_api_key()
        vega = VegaLive(ui)
        try:
            asyncio.run(vega.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down Vega...")
            try:
                flush_history()
            except Exception:
                pass

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
