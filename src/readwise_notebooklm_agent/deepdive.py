"""Create a one-source NotebookLM deep-dive workspace and matching Obsidian note.

Intended workflow:
- input is the Readwise original link / canonical article or paper URL
- one source URL becomes one NotebookLM notebook
- an additional Study Brief text source tells NotebookLM how to read it
- an Obsidian source note records the NotebookLM ID, alias, prompts, and distillation slots
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

VAULT = Path(os.environ.get("READWISE_NOTEBOOKLM_OBSIDIAN_VAULT") or os.environ.get("OBSIDIAN_VAULT") or str(Path.home() / "workspaces" / "obsidian"))
ARTICLE_DIR = VAULT / "900_Articles" / "Articles"
DEFAULT_PROFILE = os.environ.get("NLM_PROFILE", "default")


def run(cmd: list[str], *, dry_run: bool = False, capture: bool = True) -> str:
    printable = " ".join(shlex.quote(c) for c in cmd)
    if dry_run:
        print(f"DRY-RUN: {printable}")
        return ""
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    out = proc.stdout or ""
    if proc.returncode != 0:
        raise SystemExit(f"Command failed ({proc.returncode}): {printable}\n{out}")
    return out


def slugify(value: str, max_len: int = 72) -> str:
    value = value.strip()
    value = re.sub(r"https?://", "", value, flags=re.I)
    value = re.sub(r"[^\w\-가-힣一-龥ぁ-ゔァ-ヴー]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-_")
    return (value[:max_len].strip("-") or "untitled")


def safe_filename(value: str, max_len: int = 120) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "-", value).strip()
    value = re.sub(r"\s+", " ", value)
    return (value[:max_len].strip(" .-") or "Untitled")


def infer_title(url: str, explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    parsed = urlparse(url)
    path_tail = Path(parsed.path.rstrip("/")).name if parsed.path else ""
    candidate = path_tail or parsed.netloc or "Untitled Source"
    candidate = re.sub(r"[-_]+", " ", candidate)
    candidate = re.sub(r"\.pdf$", "", candidate, flags=re.I)
    return candidate.strip().title() or "Untitled Source"


def classify_source(url: str, explicit: str) -> str:
    if explicit != "auto":
        return explicit
    lower = url.lower()
    if "arxiv.org" in lower or lower.endswith(".pdf") or "/pdf/" in lower:
        return "paper"
    return "article"


def parse_notebook_id(output: str) -> str:
    # CLI versions vary. Prefer UUID-like tokens, otherwise take last long token.
    patterns = [
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        r"(?:Notebook ID|ID|notebook):\s*([A-Za-z0-9_-]{12,})",
        r"([A-Za-z0-9_-]{20,})",
    ]
    for pat in patterns:
        match = re.search(pat, output)
        if match:
            return match.group(1)
    raise SystemExit(f"Could not parse notebook ID from nlm output:\n{output}")


def make_study_brief(title: str, source_type: str, url: str, why: str, domains: list[str]) -> str:
    domain_text = ", ".join(domains) if domains else "robotics, sim2real, embodied AI, agents"
    why_text = why or "source-grounded deep dive; extract durable knowledge for Obsidian"
    return f"""# Study Brief / Reading Contract

## Source
- Title: {title}
- Source type: {source_type}
- Canonical link: {url}
- Added from: Readwise original link / canonical URL

## Why I am reading this
- {why_text}

## My default lenses
- {domain_text}

## Reading rules for NotebookLM
- Stay grounded in the uploaded source and cite relevant source passages.
- Prefer deep explanation over shallow summary.
- Separate facts, author's claims, evidence, assumptions, and my possible takeaways.
- For papers, emphasize problem setup, method, experiments, limitations, reproducibility, and robotics/sim2real relevance.
- For articles, emphasize thesis, argument chain, evidence quality, hidden assumptions, and reusable ideas.
- When uncertain, say what the source does not establish.

## Prompt ladder the agent should run
1. Preflight: one-sentence thesis, why it matters, what to skip.
2. Structure: section-by-section map of the document.
3. Contribution: problem, prior limitation, core idea, novelty, weak claims.
4. Skeptical review: assumptions, evidence gaps, failure modes, reproducibility risk.
5. Translation: robotics / sim2real / embodied AI / agent workflow implications.
6. Obsidian distillation: produce a concise source note and evergreen candidates.
"""


def yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join('"' + i.replace('"', '\\"') + '"' for i in items) + "]"


def make_obsidian_note(
    *,
    title: str,
    source_type: str,
    url: str,
    notebook_title: str,
    notebook_id: str,
    alias: str,
    why: str,
    domains: list[str],
    tags: list[str],
    today: str,
) -> str:
    type_emoji = "📄" if source_type == "paper" else "📝"
    tag_lines = tags or (["paper-reading", "notebooklm", "readwise"] if source_type == "paper" else ["article", "notebooklm", "readwise"])
    return f"""---
type: article
status: 🟦 Reading
created: {today}
started: {today}
finished:
review:
source_type: {source_type}
url: {url}
readwise_original_link: {url}
notebooklm_title: "{notebook_title.replace('"', '\\"')}"
notebooklm_notebook_id: {notebook_id or "PENDING"}
notebooklm_alias: {alias}
author:
publisher:
published:
year:
domain: {yaml_list(domains)}
importance: high
read_timing: now
distilled_note:
evergreen_note:
concept_notes: []
source_of_truth: true
tags:
""" + "\n".join(f"  - {tag}" for tag in tag_lines) + f"""
---

# {type_emoji} {title}

> Readwise original link → NotebookLM one-source deep dive → Obsidian distillation note.

## ⚡ Why this now
- {why or ""}

## 🔗 Source
- Readwise original link / canonical URL: {url}
- NotebookLM notebook: `{notebook_title}`
- NotebookLM ID: `{notebook_id or "PENDING"}`
- NotebookLM alias: `{alias}`
- Added from: Readwise original link

## 🧭 Status
- Current state: 🟦 Reading
- Next action: run NotebookLM prompt ladder and paste distilled result below
- Review date:

## 🧪 NotebookLM Prompt Ladder

### 0. Preflight
```text
이 source를 기준으로 1) 한 문장 thesis, 2) 왜 중요한지, 3) 내가 읽어야 할 부분/넘겨도 되는 부분, 4) robotics/sim2real/agent 관점 relevance를 정리해줘. 반드시 source-grounded하게 답해줘.
```

### 1. Structure Map
```text
문서를 section별로 구조화해줘. 각 section마다 목적, 핵심 주장, 필요한 배경지식, 다시 확인할 디테일을 분리해줘.
```

### 2. Contribution / Claim Audit
```text
문제 → 기존 한계 → 핵심 아이디어 → 실제 novelty → 약한 주장 → 재사용 가능한 아이디어 순서로 정리해줘.
```

### 3. Skeptical Review
```text
skeptical reviewer처럼 비판해줘. 숨은 assumption, 증거 부족, 실험/논증 약점, 실제 system 적용 시 깨질 수 있는 지점을 말해줘.
```

### 4. My Work Translation
```text
이 내용을 robotics / sim2real / embodied AI / agent workflow 관점으로 번역해줘. 내 프로젝트나 Obsidian concept note로 승격할 만한 아이디어를 뽑아줘.
```

### 5. Obsidian Distillation
```text
Obsidian에 붙일 최종 literature/source note를 만들어줘. 섹션은 TL;DR, Problem, Method/Argument, Key Ideas, Evidence, Weakness, My Use, Next Action, Evergreen Candidates로 해줘.
```

## 📌 TL;DR
- 

## ❓ Problem / Thesis
- 

## 🧪 Method / Argument
- 

## ✨ Key Ideas
- 

## 🧾 Evidence / Citations to verify
- 

## ⚠️ Weakness / Critique
- 

## 🧠 Why I care
- 

## 🗂️ Distill / Promote
- Distilled note:
- Evergreen candidates:
- Project links:

## ❓ Questions / Follow-ups
- 

## 🔗 Related Notes
- [[../📚 Article Dashboard|Article Dashboard]]
- [[../📄 Paper Dashboard|Paper Dashboard]]
- [[../Reading Pipeline|Reading Pipeline]]
"""


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for i in range(2, 100):
        candidate = path.with_name(f"{stem} {i}{suffix}")
        if not candidate.exists():
            return candidate
    raise SystemExit(f"Could not find unique filename for {path}")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="Create NotebookLM deep-dive notebook + Obsidian source note from a Readwise original link.")
    parser.add_argument("url", help="Readwise original link / canonical source URL")
    parser.add_argument("--title", help="Human-readable title. If omitted, inferred from URL path.")
    parser.add_argument("--type", choices=["auto", "article", "paper"], default="auto", help="Source type for Obsidian metadata and notebook prefix.")
    parser.add_argument("--why", default="", help="Why this source is being studied now.")
    parser.add_argument("--domain", action="append", default=[], help="Domain lens, repeatable. Example: --domain robotics --domain sim2real")
    parser.add_argument("--tag", action="append", default=[], help="Obsidian tag, repeatable.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="NotebookLM profile to use.")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for NotebookLM source processing.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands and create no external NotebookLM objects or files.")
    args = parser.parse_args(argv)

    today = dt.date.today().isoformat()
    title = infer_title(args.url, args.title)
    source_type = classify_source(args.url, args.type)
    prefix = "PAPER" if source_type == "paper" else "ARTICLE"
    notebook_title = f"[{prefix}] {today} - {title}"
    alias = f"{source_type}-{slugify(title, 42).lower()}-{today.replace('-', '')}"
    note_path = unique_path(ARTICLE_DIR / f"{safe_filename(title)}.md")

    if args.dry_run:
        print(f"Title: {title}")
        print(f"Source type: {source_type}")
        print(f"Notebook title: {notebook_title}")
        print(f"Alias: {alias}")
        print(f"Obsidian note: {note_path}")

    run(["nlm", "login", "--check", "--profile", args.profile], dry_run=args.dry_run)
    create_out = run(["nlm", "notebook", "create", notebook_title, "--profile", args.profile], dry_run=args.dry_run)
    notebook_id = "DRY_RUN_NOTEBOOK_ID" if args.dry_run else parse_notebook_id(create_out)

    source_cmd = ["nlm", "source", "add", notebook_id, "--url", args.url, "--profile", args.profile]
    if not args.no_wait:
        source_cmd.append("--wait")
    run(source_cmd, dry_run=args.dry_run)

    brief = make_study_brief(title, source_type, args.url, args.why, args.domain)
    run(["nlm", "source", "add", notebook_id, "--text", brief, "--title", "Study Brief / Reading Contract", "--profile", args.profile], dry_run=args.dry_run)
    run(["nlm", "alias", "set", alias, notebook_id, "--type", "notebook", "--profile", args.profile], dry_run=args.dry_run)

    note = make_obsidian_note(
        title=title,
        source_type=source_type,
        url=args.url,
        notebook_title=notebook_title,
        notebook_id=notebook_id,
        alias=alias,
        why=args.why,
        domains=args.domain,
        tags=args.tag,
        today=today,
    )

    if args.dry_run:
        print("\n--- Obsidian note preview ---")
        print(note[:3000])
        return 0

    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding="utf-8")
    print("Created NotebookLM deep-dive workspace")
    print(f"- Notebook: {notebook_title}")
    print(f"- Notebook ID: {notebook_id}")
    print(f"- Alias: {alias}")
    print(f"- Obsidian note: {note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
