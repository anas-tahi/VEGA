"""
build_exe.py — packages Vega into a single Windows .exe

Run from the project root:
    python build_exe.py

The finished executable will be at:
    dist/Vega/Vega.exe
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    face_png = ROOT / "face.png"
    if not face_png.exists():
        print("⚠️  face.png not found — the window icon will be missing.")
        print("   Place your assistant icon at the project root as face.png")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",                        # folder mode — faster startup than onefile
        "--windowed",                      # no terminal window when double-clicked
        "--name", "Vega",
        "--icon", str(face_png) if face_png.exists() else "NONE",

        # Data files to bundle
        "--add-data", f"{ROOT / 'core'}:core",
        "--add-data", f"{ROOT / 'config' / 'api_keys.json'}:config",
        "--add-data", f"{ROOT / 'memory'}:memory",

        # Bundle face.png at root level
        *(["--add-data", f"{face_png}:."] if face_png.exists() else []),

        # Hidden imports that PyInstaller sometimes misses
        "--hidden-import", "sounddevice",
        "--hidden-import", "google.genai",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "pyautogui",
        "--hidden-import", "pyperclip",
        "--hidden-import", "mss",
        "--hidden-import", "cv2",
        "--hidden-import", "pycaw",
        "--hidden-import", "comtypes",

        str(ROOT / "main.py"),
    ]

    print("🔨 Building Vega.exe …")
    print("   This may take 2-3 minutes.\n")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        print("\n✅ Done! Your executable is at:")
        print(f"   {ROOT / 'dist' / 'Vega' / 'Vega.exe'}")
        print("\nBefore running:")
        print("  1. Open dist/Vega/config/api_keys.json")
        print("  2. Paste your Gemini API key where it says YOUR_GEMINI_API_KEY_HERE")
        print("  3. Double-click Vega.exe — no terminal needed!")
    else:
        print("\n❌ Build failed. Check the output above for errors.")
        print("   Most common fix: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    main()
