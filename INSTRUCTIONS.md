# 📖 VEGA — Full Usage Guide

Everything you need to set up, run, and customize VEGA.

---

## 1. Installation

### Prerequisites

- **Python 3.11 or 3.12** — [download here](https://www.python.org/downloads/).
  During install, tick **"Add Python to PATH"**.
- **Google Chrome** — needed for browser and calendar tools.
- **A working microphone.**

### Steps

```bash
# 1. Clone the project
git clone https://github.com/anas-tahi/VEGA.git
cd VEGA

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install the browser automation engine
playwright install
```

---

## 2. Configuration

### Get a Gemini API key (free)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with a Google account
3. Click **Create API key**
4. Copy the key (it starts with `AIza…`)

### Add your key

Copy the example config:

```bash
# Windows
copy config\api_keys.example.json config\api_keys.json

# macOS / Linux
cp config/api_keys.example.json config/api_keys.json
```

Open `config/api_keys.json` and paste your key:

```json
{
    "gemini_api_key": "AIza_your_key_here",
    "os_system": "windows",
    "github_token": ""
}
```

> ⚠️ **Never commit `api_keys.json`.** It's already in `.gitignore`. Your key
> is private — treat it like a password.

---

## 3. First run

```bash
python main.py
```

On first launch a setup window may appear asking for your key and OS — fill it
in and you're set. When you see **"VEGA online"**, it's listening.

VEGA greets you once, then waits silently. **Just start talking.**

---

## 4. Talking to VEGA

Speak naturally in **English or Spanish** — it auto-detects and replies in the
same language. Some examples:

### Everyday
- *"What's the weather in Granada?"*
- *"Open Chrome."*
- *"Search for the latest news on AI."*
- *"Play some lofi on YouTube."*

### Files & system
- *"Create a folder called Projects on my desktop."*
- *"Find all PDFs in my Downloads."*
- *"Turn the volume down."*
- *"What's using up my disk space?"*

### Coding & projects
- *"Write a Python script that renames all files in this folder."*
- *"Review my latest git changes."*
- *"What did I commit this week?"*

### Productivity
- *"Remind me to email my professor at 3 PM."*
- *"Add a job application for Acme Corp."*
- *"Give me my weekly usage report."*

### Multi-step (agent)
- *"Research the top 3 React state libraries and save a summary to a file."*

### Ending
- Say **"shut down"**, **"exit"**, or **"apágate"** to close VEGA.

---

## 5. Customize VEGA for you

VEGA reads plain-text files in `memory/knowledge/` to personalize itself.
Edit these — no code required:

| File | What goes in it |
|------|-----------------|
| `profile.txt` | Who you are, what you do, how to address you |
| `preferences.txt` | Tone, response style, default browser/OS |
| `tech_skills.txt` | Your tech stack (helps with coding tasks) |

Add **new** `.txt` files anytime — VEGA picks them up automatically and
retrieves the relevant ones per question (TF-IDF). Example: drop a
`recipes.txt` and ask cooking questions.

### Change how it addresses you
Edit `profile.txt` and replace the name / honorific with your own.

### Change the personality
Edit `core/prompt.txt` — that's VEGA's core behavior and tone.

---

## 6. Proactive alerts

VEGA runs quiet background checks and speaks up when relevant:

- **8 AM** — today's weather
- **Monday 9 AM** — weekly usage report
- **Job follow-ups** — when an application needs a nudge

To disable, comment out the `start_alerts(self.speak)` line in `main.py`.

---

## 7. Safety & what VEGA can do

VEGA is powerful. Know how it behaves before giving it control:

- **Deleting files** → goes to the **Recycle Bin**, never permanent. Core
  folders (Desktop, Downloads, Documents, Pictures, Music, Videos, Home) are
  **protected** and can't be deleted. Individual files inside them can be, on
  request — so be clear in what you ask.
- **Running code / commands** → the agent can execute AI-generated code. Test
  on throwaway files first while you build trust.
- **Browser automation** → uses your real logged-in sessions.

Start with safe read-only tasks (searches, weather, summaries) before handing
over file or browser control.

---

## 8. Build a standalone .exe (Windows)

```bash
python build_exe.py
```

Output: `dist/Vega/Vega.exe`. Share the whole `dist/Vega/` folder; the user
still needs their own `config/api_keys.json`.

---

## 9. Troubleshooting

| Problem | Fix |
|---------|-----|
| **"No Gemini API key found"** | Make sure `config/api_keys.json` exists and your key is pasted in. |
| **No audio / mic not detected** | Run `python mic_test.py` to list devices. Check Windows mic privacy settings. |
| **`playwright` errors** | Run `playwright install` again. |
| **Browser tools fail** | Make sure Google Chrome is installed. |
| **Module not found** | Re-run `pip install -r requirements.txt`. |
| **VEGA mishears commands** | Speak clearly; reduce background noise. Charon voice works best with a decent mic. |

---

## 10. FAQ

**Does it cost money?**
The Gemini API has a free tier that's enough for personal use. Heavy use may
need a paid plan.

**Does it work offline?**
No — it needs internet for the Gemini voice model and web tools.

**Is my data sent anywhere?**
Your voice and text go to Google's Gemini API (that's how it understands you).
Your knowledge files stay local. Read Google's API terms if you're concerned.

**Can I use it on Mac/Linux?**
Partially. Voice and many tools work; some Windows-specific system controls
won't.

---

Built with ❤️ by Anas. Personal and non-commercial use only — see
[LICENSE](LICENSE).
