"""Open the screen.

    python ui.py

That is all. No virtual environment, no launcher, no `streamlit` command
on your PATH - this starts it with the SAME python that is running this
file, which is the one that has the packages installed.

It also stops any copy already running first. Streamlit re-runs app.py on
every click but does NOT re-import the modules underneath it, so an old
copy keeps serving old code and reports errors for things that are
perfectly fine.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PORT = "8501"


def stop_old() -> None:
    """Kill a copy of this app left running from before."""
    if os.name != "nt":
        subprocess.run(["pkill", "-f", "streamlit run"], check=False)
        return
    # tasklist/taskkill are always present on Windows; pkill is not, and
    # PowerShell may be restricted, so this is the dependable route.
    try:
        out = subprocess.run(
            ["wmic", "process", "where",
             "name='python.exe'", "get", "ProcessId,CommandLine"],
            capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return
    mine = str(os.getpid())
    for line in out.splitlines():
        if "streamlit" not in line.lower():
            continue
        pid = line.strip().split()[-1]
        if pid.isdigit() and pid != mine:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, check=False)
            print(f"  stopped an app already running (pid {pid})")


def main() -> int:
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("\nStreamlit is not installed yet. Run this first:\n"
              "\n    python -m pip install -r requirements.txt\n",
              file=sys.stderr)
        return 1

    stop_old()
    time.sleep(1)

    print(f"\n  Starting. Open this in your browser:\n")
    print(f"      http://localhost:{PORT}\n")
    print("  Press Ctrl+C here to stop it.\n")

    # sys.executable, not "streamlit": the command may not be on PATH, but
    # the python running this file definitely has the package.
    cmd = [sys.executable, "-m", "streamlit", "run", str(HERE / "app.py"),
           "--server.port", PORT,
           "--browser.gatherUsageStats", "false"]
    try:
        return subprocess.call(cmd, cwd=str(HERE))
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
