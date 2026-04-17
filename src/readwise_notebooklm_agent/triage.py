"""Readwise Reader API triage helper for Obsidian + NotebookLM workflows.

Reads the local Readwise token from the Obsidian Readwise plugin config by default.
It does not mutate Readwise unless --archive/--later is explicitly used.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .readwise_backend import BackendError, ReadwiseBackend, make_backend

VAULT = Path(os.environ.get("READWISE_NOTEBOOKLM_OBSIDIAN_VAULT") or os.environ.get("OBSIDIAN_VAULT") or str(Path.home() / "workspaces" / "obsidian"))
READWISE_DATA = VAULT / ".obsidian" / "plugins" / "readwise-official" / "data.json"
OUT_DIR = VAULT / "900_Articles" / "Article Inbox"
DEFAULT_DOMAIN_GROUPS: dict[str, tuple[list[str], int]] = {
    "general": (["research", "article", "paper", "guide", "tutorial", "analysis"], 1),
    "technical": (["engineering", "software", "system", "architecture", "api", "workflow"], 2),
    "ai": (["ai", "llm", "machine learning", "model", "agent", "automation"], 2),
}


class DomainConfigError(ValueError):
    """Raised when a custom domain scoring config has an invalid schema."""


def _normalize_domain_config(raw: dict) -> dict[str, tuple[list[str], int]]:
    if not isinstance(raw, dict):
        raise DomainConfigError("domain config must be a JSON object")
    groups: dict[str, tuple[list[str], int]] = {}
    for name, spec in raw.items():
        if isinstance(spec, dict):
            keywords = spec.get("keywords", [])
            weight_value = spec.get("weight", 3)
        elif isinstance(spec, list):
            keywords = spec
            weight_value = 3
        else:
            raise DomainConfigError(f"domain {name!r} must be an object or keyword list")
        if isinstance(keywords, str) or not isinstance(keywords, list):
            raise DomainConfigError(f"domain {name!r} keywords must be a list")
        try:
            weight = int(weight_value)
        except (TypeError, ValueError) as exc:
            raise DomainConfigError(f"domain {name!r} weight must be an integer") from exc
        groups[str(name)] = ([str(k).lower() for k in keywords], weight)
    return groups


def load_domain_groups(domains_file: str | None = None) -> dict[str, tuple[list[str], int]]:
    domains_file = domains_file or os.environ.get("READWISE_NOTEBOOKLM_DOMAINS_FILE")
    groups = dict(DEFAULT_DOMAIN_GROUPS)
    if domains_file:
        with open(domains_file, "r", encoding="utf-8") as f:
            custom = _normalize_domain_config(json.load(f))
        groups.update(custom)
    return groups


def load_token() -> str:
    env = os.environ.get("READWISE_TOKEN")
    if env:
        return env.strip()
    if READWISE_DATA.exists():
        data = json.loads(READWISE_DATA.read_text())
        token = data.get("token")
        if token:
            return token
    raise SystemExit("No Readwise token found. Set READWISE_TOKEN or configure Obsidian Readwise plugin.")


def kst_days_ago_iso(days: int) -> str:
    # Convert KST local start time to UTC ISO for Readwise API.
    kst = dt.timezone(dt.timedelta(hours=9))
    now_kst = dt.datetime.now(kst)
    start_kst = (now_kst - dt.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_kst.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def score_doc(doc: dict, domains: list[str], keyword_groups: dict[str, tuple[list[str], int]] | None = None) -> tuple[int, list[str]]:
    text = " ".join(str(doc.get(k) or "") for k in ["title", "summary", "source_url", "url", "site_name", "notes", "category"]).lower()
    tags = doc.get("tags") or {}
    text += " " + " ".join(tags.keys() if isinstance(tags, dict) else [str(tags)])
    keyword_groups = keyword_groups or DEFAULT_DOMAIN_GROUPS
    selected = domains or list(keyword_groups)
    score = 0
    reasons = []
    for domain in selected:
        kws, weight = keyword_groups.get(domain, ([domain], 3))
        hits = [k for k in kws if k in text]
        if hits:
            inc = weight * min(3, len(hits))
            score += inc
            reasons.append(f"{domain}: {', '.join(hits[:3])}")
    if doc.get("location") == "new":
        score += 4
    if doc.get("category") == "rss":
        score -= 2
    src = (doc.get("source_url") or doc.get("url") or "").lower()
    if any(x in src for x in ["linkedin.com", "x.com", "twitter.com", "threads.com"]):
        score -= 1
        reasons.append("needs-browser-fallback")
    if any(x in src for x in ["arxiv.org", "github.com", "openai.com", "nvidia.com", "substack.com"]):
        score += 2
        reasons.append("notebooklm-friendly-url")
    return score, reasons


def classify_type(doc: dict) -> str:
    src = (doc.get("source_url") or doc.get("url") or "").lower()
    title = (doc.get("title") or "").lower()
    if doc.get("category") == "pdf" or "arxiv.org" in src or src.endswith(".pdf") or "paper" in title:
        return "paper"
    return "article"


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def print_docs(items: list[tuple[int, list[str], dict]], top: int) -> None:
    for rank, (score, reasons, d) in enumerate(items[:top], 1):
        src = d.get("source_url") or d.get("url") or ""
        print(f"{rank:02d}. [{score:>3}] {d.get('title')}")
        print(f"    id: {d.get('id')} | {d.get('location')} | {d.get('category')} | {d.get('updated_at')}")
        print(f"    url: {src}")
        if reasons:
            print(f"    why: {' | '.join(reasons[:5])}")
        summary = re.sub(r"\s+", " ", d.get("summary") or "").strip()
        if summary:
            print(f"    summary: {summary[:280]}")
        print()


def write_obsidian(items: list[tuple[int, list[str], dict]], top: int, out: Path | None = None) -> Path:
    today = dt.datetime.now().date().isoformat()
    out = out or OUT_DIR / f"Readwise API Triage - {today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 📥 Readwise API Triage - {today}",
        "",
        "> Generated by `readwise-api-triage` from Reader API v3.",
        "",
        "## 🔥 Top Candidates",
        "",
    ]
    for rank, (score, reasons, d) in enumerate(items[:top], 1):
        src = d.get("source_url") or d.get("url") or ""
        title = d.get("title") or "Untitled"
        lines += [
            f"{rank}. [{title}]({src})",
            f"   - Score: {score}",
            f"   - Reader ID: `{d.get('id')}`",
            f"   - Location/category: `{d.get('location')}` / `{d.get('category')}`",
            f"   - Why: {' | '.join(reasons[:5]) if reasons else ''}",
        ]
        summary = re.sub(r"\s+", " ", d.get("summary") or "").strip()
        if summary:
            lines.append(f"   - Summary: {summary[:500]}")
        cmd = make_nlm_command(d, reasons)
        lines += ["   - Handoff:", "", "     ```bash", f"     {cmd}", "     ```", ""]
    lines += [
        "## 🦞 OpenClaw Rule",
        "",
        "Use OpenClaw only when `source_url` is a logged-in/social page or NotebookLM URL import fails.",
        "Public arXiv/GitHub/blog URLs should go straight to `readwise-nlm-deepdive`.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def domains_from_reasons(reasons: list[str]) -> list[str]:
    domains: list[str] = []
    for reason in reasons:
        if ":" not in reason:
            continue
        domain = reason.split(":", 1)[0].strip()
        if domain and domain not in domains and domain != "needs-browser-fallback":
            domains.append(domain)
    return domains


def make_nlm_command(doc: dict, reasons: list[str]) -> str:
    src = doc.get("source_url") or doc.get("url") or ""
    title = doc.get("title") or "Untitled"
    typ = classify_type(doc)
    why = (doc.get("summary") or "Readwise API triage candidate")[:220].replace("\n", " ")
    domains = domains_from_reasons(reasons)
    parts = ["readwise-nlm-deepdive", shell_quote(src), "--title", shell_quote(title), "--type", typ, "--why", shell_quote(why)]
    for d in domains[:4]:
        parts += ["--domain", d]
    parts += ["--tag", "readwise", "--tag", "notebooklm"]
    return " ".join(parts)


def to_nlm(doc: dict, reasons: list[str], dry_run: bool) -> int:
    # Use shell for robust Korean/quote handling from make_nlm_command.
    command = make_nlm_command(doc, reasons)
    if dry_run:
        print(command)
        return 0
    return subprocess.call(command, shell=True)


def update_docs(backend: ReadwiseBackend, ids: list[str], *, location: str | None, tags: list[str] | None, dry_run: bool) -> None:
    updates=[]
    for idv in ids:
        u={"id": idv}
        if location:
            u["location"] = location
        if tags is not None:
            u["tags"] = tags
        updates.append(u)
    print(json.dumps(backend.update_documents(updates, dry_run=dry_run), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    ap=argparse.ArgumentParser(description="Triage Readwise Reader documents and hand off selected items to NotebookLM/Obsidian.")
    ap.add_argument("--days", type=int, default=7, help="KST days back, converted to UTC updatedAfter.")
    ap.add_argument("--updated-after", help="Explicit UTC ISO updatedAfter override.")
    ap.add_argument("--location", choices=["new", "later", "shortlist", "archive", "feed"], help="Reader location filter.")
    ap.add_argument("--category", choices=["article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"], help="Reader category filter.")
    ap.add_argument("--tag", action="append", default=[], help="Reader tag filter; repeatable, AND semantics.")
    ap.add_argument("--domain", action="append", default=[], help="Scoring domain name from built-ins or --domains-file; repeatable.")
    ap.add_argument("--domains-file", help="Optional JSON domain keyword config merged over built-ins. Can also be set with READWISE_NOTEBOOKLM_DOMAINS_FILE.")
    ap.add_argument("--backend", choices=["auto", "readwise-cli", "api"], default=os.environ.get("READWISE_NOTEBOOKLM_BACKEND", "auto"), help="Readwise data backend. Default: auto (official readwise CLI if available, otherwise API).")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--pages", type=int, default=3, help="Max API pages of 100 docs.")
    ap.add_argument("--write-obsidian", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--to-nlm", help="Reader document id to send to readwise-nlm-deepdive.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--archive", nargs="*", help="Move given Reader document IDs to archive.")
    ap.add_argument("--later", nargs="*", help="Move given Reader document IDs to later.")
    args=ap.parse_args(argv)
    try:
        backend = make_backend(args.backend, token_loader=load_token)
    except BackendError as exc:
        raise SystemExit(str(exc)) from exc
    if args.archive is not None:
        update_docs(backend, args.archive, location="archive", tags=None, dry_run=args.dry_run); return 0
    if args.later is not None:
        update_docs(backend, args.later, location="later", tags=None, dry_run=args.dry_run); return 0
    try:
        keyword_groups = load_domain_groups(args.domains_file)
    except (OSError, json.JSONDecodeError, DomainConfigError) as exc:
        raise SystemExit(f"Could not load domain config: {exc}") from exc
    updated_after=args.updated_after or kst_days_ago_iso(args.days)
    docs=backend.list_documents(updated_after=updated_after, location=args.location, category=args.category, tag=args.tag, limit_pages=args.pages, with_html=False, with_raw=False)
    items=[]
    for d in docs:
        score, reasons = score_doc(d, args.domain, keyword_groups)
        if score > 0:
            items.append((score, reasons, d))
    items.sort(key=lambda x: (x[0], x[2].get("updated_at") or ""), reverse=True)
    if args.to_nlm:
        for score, reasons, d in items:
            if d.get("id") == args.to_nlm:
                return to_nlm(d, reasons, args.dry_run)
        # Fetch by id if not in the filtered window.
        doc = backend.get_document(args.to_nlm)
        if not doc:
            raise SystemExit(f"Document not found: {args.to_nlm}")
        score,reasons=score_doc(doc, args.domain, keyword_groups)
        return to_nlm(doc, reasons, args.dry_run)
    print(f"Fetched {len(docs)} docs since {updated_after} via {backend.name}; scored {len(items)} candidates.")
    print_docs(items, args.top)
    if args.write_obsidian:
        out=write_obsidian(items, args.top, args.out)
        print(f"Wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
