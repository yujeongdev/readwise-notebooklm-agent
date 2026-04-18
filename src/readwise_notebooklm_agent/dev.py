"""Developer/agent verification helpers."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def check() -> int:
    """Run the standard local verification suite."""
    run([sys.executable, "-m", "compileall", "src", "tests"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "-m", "readwise_notebooklm_agent.triage", "--help"])
    run([sys.executable, "-m", "readwise_notebooklm_agent.deepdive", "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
