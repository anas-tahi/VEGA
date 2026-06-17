"""
mic_test.py — run this BEFORE main.py to diagnose mic issues.
Usage: python mic_test.py

It will:
1. List all devices
2. Try recording 3 seconds from device #1
3. Print the RMS (volume level) — should be > 100 when you speak
4. Save a test.wav so you can verify the recording
"""

import sounddevice as sd
import numpy as np
import wave
import sys

DEVICE      = 1          # Realtek device that worked in the test
SAMPLERATE  = 16000
CHANNELS    = 1
DURATION    = 3          # seconds to record
DTYPE       = "int16"

print("=" * 50)
print("VEGA MIC DIAGNOSTIC")
print("=" * 50)

# 1. List devices
print("\n📋 All audio devices:")
devices = sd.query_devices()
for i, d in enumerate(devices):
    ch_in  = d.get("max_input_channels", 0)
    ch_out = d.get("max_output_channels", 0)
    tag    = "INPUT " if ch_in > 0 else "output"
    print(f"  [{i}] {tag}  {d['name']}  (sr={d['default_samplerate']})")

print(f"\n🎤 Testing device #{DEVICE} at {SAMPLERATE}Hz for {DURATION}s...")
print("👉 SPEAK NOW into your mic!\n")

try:
    recording = sd.rec(
        int(DURATION * SAMPLERATE),
        samplerate=SAMPLERATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=DEVICE,
    )
    sd.wait()

    rms = int(np.sqrt(np.mean(recording.astype(np.float32) ** 2)))
    peak = int(np.max(np.abs(recording)))
    print(f"✅ Recording done.")
    print(f"   RMS  = {rms}   (should be >200 when speaking, 0 = no audio)")
    print(f"   Peak = {peak}  (should be >500 when speaking)")

    if rms < 50:
        print("\n❌ RESULT: Mic is returning silence.")
        print("   Possible causes:")
        print("   1. Wrong device — try changing DEVICE = 1 to another input index above")
        print("   2. Windows privacy still blocking — check Settings > Privacy > Microphone")
        print("   3. Mic muted in Windows sound mixer")
    else:
        print(f"\n✅ RESULT: Mic is working! RMS={rms}")
        print("   The audio pipeline should work.")

    # Save wav for manual inspection
    with wave.open("mic_test.wav", "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLERATE)
        wf.writeframes(recording.tobytes())
    print("\n💾 Saved recording to mic_test.wav — play it to hear what was captured.")

except Exception as e:
    print(f"\n❌ Recording failed: {e}")
    print("\nTrying each input device one by one...")
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            try:
                rec = sd.rec(int(0.5 * SAMPLERATE), samplerate=SAMPLERATE,
                             channels=1, dtype="int16", device=i)
                sd.wait()
                rms = int(np.sqrt(np.mean(rec.astype(np.float32) ** 2)))
                print(f"  Device #{i} ({d['name']}): RMS={rms} ✅")
            except Exception as e2:
                print(f"  Device #{i} ({d['name']}): FAILED — {e2}")

print("\n" + "=" * 50)
