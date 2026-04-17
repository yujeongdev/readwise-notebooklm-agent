# CLAUDE.md - Agent Usage Guide

Claude/Codex/OpenClaw agents should treat this repo as a small, reliable tool
surface for Readwise Reader triage and NotebookLM deep dives.

## Fast Path

If asked "Readwise에서 읽을만한 것 뽑아줘":

```bash
readwise-api-triage --days 7 --location new \
  --domain robotics --domain vla --domain sim2real \
  --top 20 --write-obsidian
```

If asked to deep-dive one Reader item:

```bash
readwise-api-triage --days 7 --location new \
  --domain robotics --domain vla --domain sim2real \
  --to-nlm <reader-document-id>
```

If given a URL directly:

```bash
readwise-nlm-deepdive "<url>" --title "<title>" --type article --why "<reason>"
```

## What to Report

After running triage, report:

- the Obsidian triage note path;
- top 3-5 candidates with reasons;
- which items need OpenClaw/browser fallback;
- any API or auth blocker.

After running a deep dive setup, report:

- NotebookLM title;
- NotebookLM ID or alias;
- Obsidian note path;
- whether source import succeeded;
- next prompt ladder step.

## Do Not

- Do not print tokens.
- Do not commit private Readwise export data.
- Do not bulk-create NotebookLM notebooks unless the user explicitly asks.
- Do not use browser automation when a clean public `source_url` is available.
- Do not mutate Readwise state without `--dry-run` first unless explicitly told.
