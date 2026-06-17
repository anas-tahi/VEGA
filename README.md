# 🤖 VEGA
### Your personal bilingual AI assistant — by Anas

A real-time voice AI that hears, sees, and controls your computer.
Speaks **English and Spanish** — just talk and it matches your language.

---

## ✨ Features

- 🎙️ **Real-time voice** — speaks English & Spanish, auto-detects your language
- 🧠 **Smart memory (RAG)** — TF-IDF retrieval over your personal knowledge base
- 🖥️ **Full computer control** — apps, files, browser, settings, mouse & keyboard
- 🤖 **Autonomous agent** — plans and executes multi-step tasks with result chaining
- 🔔 **Proactive alerts** — weather, deadlines, and follow-up reminders without being asked
- 🐙 **GitHub summary** — *"what did I commit this week?"*
- 🎮 **Game updater, flight finder, job tracker, UGR portal** and 25 tools total
- 🎤 **Smart microphone** auto-detection — no manual device config

---

## ⚡ Quick start

```bash
git clone <your-repo>
cd vega
pip install -r requirements.txt
playwright install
```

Open `config/api_keys.json` and paste your Gemini API key:

```json
{
    "gemini_api_key": "AIza...",
    "os_system": "windows",
    "github_token": ""
}
```

Get your key free at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

Run:
```bash
python main.py
```

---

## 🖥️ Build the desktop .exe (Windows)

```bash
python build_exe.py
```

The finished app is at `dist/Vega/Vega.exe`.

---

## 🔔 Proactive alerts (new)

VEGA now speaks up without being asked:
- **8 AM** — Today's weather in Granada
- **Monday 9 AM** — Weekly usage report
- **Any time** — Job application follow-up reminders
- **Morning** — Upcoming PRADO deadlines (if cached)

---

## 🐙 GitHub activity summary (new)

Say: *"What did I commit this week?"* or *"Show my GitHub activity"*

Add your GitHub username to `memory/knowledge/anas_profile.txt`:
```
GitHub username: yourusername
```

Optionally add a token to `config/api_keys.json` for private repos:
```json
"github_token": "ghp_..."
```

---

## 🎙️ Voice

Just speak — VEGA detects whether you're speaking English or Spanish
and replies in the same language.

---

## 📋 Requirements

- Windows 10/11 (Linux/macOS partially supported)
- Python 3.11 or 3.12
- Microphone
- [Gemini API key](https://aistudio.google.com/app/apikey) (for voice)
- Google Chrome (for calendar + browser tools)

---

## ⚠️ License

See the [LICENSE](LICENSE) file. Personal and non-commercial use only.
