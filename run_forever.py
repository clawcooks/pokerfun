"""Auto-restart wrapper — keeps play_lobby.py running indefinitely."""
import subprocess
import sys
import time

script = "play_lobby.py"
attempt = 0

while True:
    attempt += 1
    print(f"\n[run_forever] Starting attempt #{attempt}...", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=r"C:\Users\victo\Downloads\pokerfun",
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        print(f"[run_forever] Exited with code {result.returncode}", flush=True)
    except Exception as e:
        print(f"[run_forever] Exception: {e}", flush=True)
    time.sleep(5)
