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


def _kill(pid: str, mine: str) -> None:
    if pid.isdigit() and pid != mine:
        subprocess.run(["taskkill", "/F", "/PID", pid],
                       capture_output=True, check=False)
        print(f"  stopped an app already running (pid {pid})")


def stop_old() -> None:
    """Kill a copy of this app left running from before.

    The important case is a Streamlit server started earlier from a different
    checkout (D:\\tushar\\ontology): the browser keeps showing that old app and
    its errors, while a new `python ui.py` looks broken. wmic is deprecated and
    missing on some Windows 11 installs, so the port owner is checked first.
    """
    mine = str(os.getpid())
    if os.name != "nt":
        subprocess.run(["pkill", "-f", "streamlit run"], check=False)
        return

    # 1) whoever is listening on the port this app is about to use
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"],
                             capture_output=True, text=True, timeout=20).stdout
        for line in out.splitlines():
            parts = line.split()
            if (len(parts) >= 5 and parts[1].endswith(f":{PORT}")
                    and parts[3].upper() == "LISTENING"):
                _kill(parts[4], mine)
    except Exception:                            # noqa: BLE001 - best effort
        pass

    # 2) any python process whose command line runs streamlit
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { "
             "$_.Name -eq 'python.exe' -and $_.CommandLine -match 'streamlit' }"
             " | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=20).stdout
        for pid in out.split():
            _kill(pid.strip(), mine)
    except Exception:                            # noqa: BLE001 - best effort
        pass


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
