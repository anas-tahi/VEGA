<div align="center">

# 🤖 VEGA

### Your personal bilingual AI assistant

**A real-time voice AI that hears, sees, and controls your computer.**
Speaks **English & Spanish** — just talk, and it matches your language.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-Personal-orange)
![Powered by Gemini](https://img.shields.io/badge/powered%20by-Gemini-4285F4)

</div>

---

## ✨ Features

- 🎙️ **Real-time voice** — speaks English & Spanish, auto-detects your language
- 🧠 **Smart memory (RAG)** — TF-IDF retrieval over your personal knowledge base
- 🖥️ **Full computer control** — apps, files, browser, settings, mouse & keyboard
- 🤖 **Autonomous agent** — plans and executes multi-step tasks with result chaining
- 🔔 **Proactive alerts** — weather, deadlines, and follow-up reminders without being asked
- 🐙 **GitHub summary** — *"what did I commit this week?"*
- 🎮 **25 tools total** — game updater, flight finder, job tracker, UGR portal & more
- 🎤 **Smart microphone** auto-detection — no manual device config

---

## ⚡ Quick start

```bash
git clone https://github.com/anas-tahi/VEGA.git
cd VEGA
pip install -r requirements.txt
playwright install
```

Copy the example config and add your Gemini API key:

```bash
copy config\api_keys.example.json config\api_keys.json   # Windows
```

Then open `config/api_keys.json` and paste your key:

```json
{
    "gemini_api_key": "AIza...",
    "os_system": "windows",
    "github_token": ""
}
```

> Get your free Gemini API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

Run it:

```bash
python main.py
```

---

## ⚠️ Safety — read before running

VEGA is a **powerful** assistant. It can run code, manage files, control your
mouse and keyboard, change system settings, and automate your browser. Please
understand what that means:

- **File deletion** sends files to the **Recycle Bin** (never permanent), and
  core folders (Desktop, Downloads, Documents, etc.) are **protected** from
  deletion. Individual files inside them can still be removed on request.
- **Code & command execution** — the agent can run AI-generated code and
  commands. Test on non-critical files first until you trust it.
- **Browser automation** logs into your real accounts (calendar, portals).
- VEGA is provided **as-is, with no warranty**. You run it at your own risk.
  See [LICENSE](LICENSE).

If you're unsure, start with read-only tasks (searches, weather, summaries)
before giving it control of files or your browser.

---

## 🖥️ Build the desktop .exe (Windows)

```bash
python build_exe.py
```

The finished app appears at `dist/Vega/Vega.exe`.

---

## 🔔 Proactive alerts

VEGA speaks up on its own when something's worth your attention:

| When | What |
|------|------|
| 8 AM | Today's weather |
| Monday 9 AM | Weekly usage report |
| Any time | Job application follow-up reminders |
| Morning | Upcoming deadlines (if cached) |

---

## 🐙 GitHub activity summary

Say: *"What did I commit this week?"* or *"Show my GitHub activity."*

Set your GitHub username in `memory/knowledge/profile.txt`:

```
GitHub username: yourusername
```

*(Optional)* add a token to `config/api_keys.json` for private repos:

```json
"github_token": "ghp_..."
```

---

## 🎙️ Voice

Just speak. VEGA detects whether you're using English or Spanish and replies
in the same language — no setting to toggle.

---

## 📋 Requirements

- Windows 10/11 (Linux/macOS partially supported)
- Python 3.11 or 3.12
- A microphone
- [Gemini API key](https://aistudio.google.com/app/apikey) (for voice)
- Google Chrome (for calendar + browser tools)

---

## 📂 Project structure

```
VEGA/
├── main.py            # Entry point — voice session & tool dispatch
├── ui.py              # PyQt6 heads-up display
├── core/              # System prompt
├── agent/             # Planner, executor, task queue, error handling
├── actions/           # 25 tools (files, browser, GitHub, weather…)
├── memory/            # RAG, history, long-term memory, knowledge base
└── config/            # API keys (gitignored) + example
```

---

## 📖 Full usage guide

See **[INSTRUCTIONS.md](INSTRUCTIONS.md)** for setup details, voice commands,
customization, and troubleshooting.

---

## ⚠️ License

See the [LICENSE](LICENSE) file. Personal and non-commercial use only.
