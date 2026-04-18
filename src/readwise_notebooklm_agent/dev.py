"""Developer/agent verification helpers."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() and (cwd / "tests").is_dir():
        return cwd
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists() and (parent / "tests").is_dir():
            return parent
    raise SystemExit("readwise-notebooklm-check must be run from the project checkout")


ROOT = find_project_root()


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def check() -> int:
    """Run the standard local verification suite."""
    run([sys.executable, "-m", "compileall", "src", "tests"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run([sys.executable, "-m", "readwise_notebooklm_agent.triage", "--help"])
    run([sys.executable, "-m", "readwise_notebooklm_agent.deepdive", "--help"])
    run([sys.executable, "-m", "readwise_notebooklm_agent.skills", "--help"])
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
