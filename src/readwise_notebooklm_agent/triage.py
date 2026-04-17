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
import time
import urllib.parse
import urllib.request
from pathlib import Path

VAULT = Path(os.environ.get("READWISE_NOTEBOOKLM_OBSIDIAN_VAULT") or os.environ.get("OBSIDIAN_VAULT") or str(Path.home() / "workspaces" / "obsidian"))
READWISE_DATA = VAULT / ".obsidian" / "plugins" / "readwise-official" / "data.json"
OUT_DIR = VAULT / "900_Articles" / "Article Inbox"
API_BASE = "https://readwise.io/api/v3"

KEYWORD_GROUPS = {
    "robotics": (["robot", "robotics", "robotic", "manipulation", "humanoid", "dexterous", "gripper", "tactile"], 6),
    "vla": (["vla", "vision-language-action", "vision language action", "embodied", "physical ai", "gemini robotics"], 7),
    "sim2real": (["sim2real", "sim-to-real", "real2sim", "simulation", "simulator", "digital twin", "omniverse", "isaac", "mujoco", "physics-aware", "synthetic data"], 6),
    "rl": (["reinforcement", " rl", "reward", "policy", "imitation", "preference", "benchmark", "stage-aware"], 4),
    "agents": (["agent", "codex", "claude code", "openclaw", "mcp", "harness", "context", "multi-agent", "agentic", "knowledge base"], 5),
    "infra": (["vllm", "serving", "gpu", "cluster", "inference", "pagedattention", "kubernetes", "osmo"], 3),
    "career": (["career", "resume", "cv", "portfolio", "hiring", "job", "이력서", "채용", "생존"], 3),
}


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


def request_json(path: str, params: dict[str, str], token: str, method: str = "GET", body: dict | None = None) -> dict:
    query = ("?" + urllib.parse.urlencode(params, doseq=True)) if params else ""
    data = None
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API_BASE + path + query, data=data, headers=headers, method=method)
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", "5"))
                print(f"Rate limited; sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            detail = e.read().decode("utf-8", "replace")[:500]
            raise SystemExit(f"Readwise API error {e.code}: {detail}")


def kst_days_ago_iso(days: int) -> str:
    # Convert KST local start time to UTC ISO for Readwise API.
    kst = dt.timezone(dt.timedelta(hours=9))
    now_kst = dt.datetime.now(kst)
    start_kst = (now_kst - dt.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_kst.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_docs(token: str, *, updated_after: str | None, location: str | None, category: str | None, tag: list[str], limit_pages: int, with_html: bool, with_raw: bool) -> list[dict]:
    docs: list[dict] = []
    cursor = None
    pages = 0
    while True:
        params: dict[str, str | list[str]] = {"limit": "100"}
        if cursor:
            params["pageCursor"] = cursor
        elif updated_after:
            params["updatedAfter"] = updated_after
        if location:
            params["location"] = location
        if category:
            params["category"] = category
        if tag:
            params["tag"] = tag
        if with_html:
            params["withHtmlContent"] = "true"
        if with_raw:
            params["withRawSourceUrl"] = "true"
        data = request_json("/list/", params, token)
        docs.extend(data.get("results", []))
        cursor = data.get("nextPageCursor")
        pages += 1
        if not cursor or pages >= limit_pages:
            break
    return docs


def score_doc(doc: dict, domains: list[str]) -> tuple[int, list[str]]:
    text = " ".join(str(doc.get(k) or "") for k in ["title", "summary", "source_url", "url", "site_name", "notes", "category"]).lower()
    tags = doc.get("tags") or {}
    text += " " + " ".join(tags.keys() if isinstance(tags, dict) else [str(tags)])
    selected = domains or ["robotics", "vla", "sim2real", "rl", "agents", "infra", "career"]
    score = 0
    reasons = []
    for domain in selected:
        kws, weight = KEYWORD_GROUPS.get(domain, ([domain], 3))
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


def make_nlm_command(doc: dict, reasons: list[str]) -> str:
    src = doc.get("source_url") or doc.get("url") or ""
    title = doc.get("title") or "Untitled"
    typ = classify_type(doc)
    why = (doc.get("summary") or "Readwise API triage candidate")[:220].replace("\n", " ")
    domains = []
    joined = " ".join(reasons).lower()
    for d in ["robotics", "sim2real", "vla", "rl", "agents", "infra", "career"]:
        if d in joined:
            domains.append(d)
    if not domains:
        domains = ["robotics"]
    parts = ["readwise-nlm-deepdive", shell_quote(src), "--title", shell_quote(title), "--type", typ, "--why", shell_quote(why)]
    for d in domains[:4]:
        parts += ["--domain", d]
    parts += ["--tag", "readwise", "--tag", "notebooklm"]
    return " ".join(parts)


def to_nlm(doc: dict, reasons: list[str], dry_run: bool) -> int:
    cmd = make_nlm_command(doc, reasons).split(" ")
    # Use shell for robust Korean/quote handling from make_nlm_command.
    command = make_nlm_command(doc, reasons)
    if dry_run:
        print(command)
        return 0
    return subprocess.call(command, shell=True)


def update_docs(token: str, ids: list[str], *, location: str | None, tags: list[str] | None, dry_run: bool) -> None:
    updates=[]
    for idv in ids:
        u={"id": idv}
        if location:
            u["location"] = location
        if tags is not None:
            u["tags"] = tags
        updates.append(u)
    if dry_run:
        print(json.dumps({"updates": updates}, ensure_ascii=False, indent=2))
        return
    print(json.dumps(request_json("/bulk_update/", {}, token, method="PATCH", body={"updates": updates}), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    ap=argparse.ArgumentParser(description="Triage Readwise Reader documents and hand off selected items to NotebookLM/Obsidian.")
    ap.add_argument("--days", type=int, default=7, help="KST days back, converted to UTC updatedAfter.")
    ap.add_argument("--updated-after", help="Explicit UTC ISO updatedAfter override.")
    ap.add_argument("--location", choices=["new", "later", "shortlist", "archive", "feed"], help="Reader location filter.")
    ap.add_argument("--category", choices=["article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"], help="Reader category filter.")
    ap.add_argument("--tag", action="append", default=[], help="Reader tag filter; repeatable, AND semantics.")
    ap.add_argument("--domain", action="append", default=[], help="Scoring domain: robotics, vla, sim2real, rl, agents, infra, career; repeatable.")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--pages", type=int, default=3, help="Max API pages of 100 docs.")
    ap.add_argument("--write-obsidian", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--to-nlm", help="Reader document id to send to readwise-nlm-deepdive.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--archive", nargs="*", help="Move given Reader document IDs to archive.")
    ap.add_argument("--later", nargs="*", help="Move given Reader document IDs to later.")
    args=ap.parse_args(argv)
    token=load_token()
    if args.archive is not None:
        update_docs(token, args.archive, location="archive", tags=None, dry_run=args.dry_run); return 0
    if args.later is not None:
        update_docs(token, args.later, location="later", tags=None, dry_run=args.dry_run); return 0
    updated_after=args.updated_after or kst_days_ago_iso(args.days)
    docs=fetch_docs(token, updated_after=updated_after, location=args.location, category=args.category, tag=args.tag, limit_pages=args.pages, with_html=False, with_raw=False)
    items=[]
    for d in docs:
        score, reasons = score_doc(d, args.domain)
        if score > 0:
            items.append((score, reasons, d))
    items.sort(key=lambda x: (x[0], x[2].get("updated_at") or ""), reverse=True)
    if args.to_nlm:
        for score, reasons, d in items:
            if d.get("id") == args.to_nlm:
                return to_nlm(d, reasons, args.dry_run)
        # fetch by id if not in filtered window
        exact=fetch_docs(token, updated_after=None, location=None, category=None, tag=[], limit_pages=1, with_html=False, with_raw=False)
        for d in exact:
            if d.get("id") == args.to_nlm:
                score, reasons=score_doc(d,args.domain)
                return to_nlm(d,reasons,args.dry_run)
        data=request_json("/list/", {"id": args.to_nlm, "limit":"1"}, token)
        docs2=data.get("results", [])
        if not docs2:
            raise SystemExit(f"Document not found: {args.to_nlm}")
        score,reasons=score_doc(docs2[0], args.domain)
        return to_nlm(docs2[0], reasons, args.dry_run)
    print(f"Fetched {len(docs)} docs since {updated_after}; scored {len(items)} candidates.")
    print_docs(items, args.top)
    if args.write_obsidian:
        out=write_obsidian(items, args.top, args.out)
        print(f"Wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
