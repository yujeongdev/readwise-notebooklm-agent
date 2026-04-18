"""Install bundled agent skills for Codex, Claude, and generic agents."""
from __future__ import annotations

import argparse
import filecmp
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

SKILL_NAME = "readwise-notebooklm-deepdive"
TARGET_DIRS = {
    "codex": Path(".codex/skills"),
    "claude": Path(".claude/skills"),
    "agents": Path(".agents/skills"),
}


@dataclass(frozen=True)
class InstallResult:
    target: str
    path: Path
    action: str


def template_dir() -> Path:
    """Return the packaged skill template directory."""
    return Path(str(resources.files("readwise_notebooklm_agent") / "skill_templates" / SKILL_NAME))


def default_targets() -> list[str]:
    return ["codex", "claude", "agents"]


def install_skill(
    *,
    home: Path,
    targets: Iterable[str],
    force: bool = False,
    dry_run: bool = False,
) -> list[InstallResult]:
    """Install the bundled skill into one or more agent skill homes."""
    source = template_dir()
    if not (source / "SKILL.md").is_file():
        raise FileNotFoundError(f"Bundled skill template is missing: {source}")

    results: list[InstallResult] = []
    for target in targets:
        if target not in TARGET_DIRS:
            valid = ", ".join(sorted(TARGET_DIRS))
            raise ValueError(f"Unknown target '{target}'. Expected one of: {valid}")

        destination = home / TARGET_DIRS[target] / SKILL_NAME
        destination_file = destination / "SKILL.md"
        if destination_file.exists() and filecmp.cmp(source / "SKILL.md", destination_file, shallow=False):
            results.append(InstallResult(target, destination, "unchanged"))
            continue
        if destination.exists() and not force:
            results.append(InstallResult(target, destination, "skipped-existing"))
            continue
        if dry_run:
            action = "would-update" if destination.exists() else "would-create"
            results.append(InstallResult(target, destination, action))
            continue

        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        results.append(InstallResult(target, destination, "updated"))
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install bundled Readwise → NotebookLM agent skills.")
    parser.add_argument(
        "--target",
        choices=sorted(TARGET_DIRS),
        action="append",
        help="Skill host to install into. Repeatable. Defaults to codex, claude, and agents.",
    )
    parser.add_argument("--home", type=Path, default=Path.home(), help=argparse.SUPPRESS)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing skill directory.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    targets = args.target or default_targets()
    results = install_skill(home=args.home.expanduser(), targets=targets, force=args.force, dry_run=args.dry_run)
    for result in results:
        print(f"{result.target}: {result.action}: {result.path}")
    if any(result.action == "skipped-existing" for result in results):
        print("Use --force to overwrite existing skill directories.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
