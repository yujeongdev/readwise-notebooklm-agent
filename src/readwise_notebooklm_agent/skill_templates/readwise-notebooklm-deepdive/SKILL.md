---
name: readwise-notebooklm-deepdive
description: "Use when the user wants to study a Readwise original link, article, or paper by creating one NotebookLM notebook per source and recording the workflow in Obsidian. Triggers on Readwise original link, NotebookLM deep dive, one article one notebook, one paper one notebook, article/paper study workflow, or source-grounded reading automation."
---

# Readwise → NotebookLM → Obsidian Deep Dive

Use this skill to run the `readwise-notebooklm-agent` workflow instead of writing one-off glue code.

## Implementation Backend

This skill is backed by the local `readwise-notebooklm-agent` package.

Backend details:

- **Package**: `readwise-notebooklm-agent`
- **Repository**: `https://github.com/yujeongdev/readwise-notebooklm-agent`
- **Install/update package**: `uv tool install --force /path/to/readwise-notebooklm-agent`
- **Install/update skills**: `readwise-notebooklm-install-skills --force`
- **Console scripts**:
  - `readwise-nlm-deepdive` → one-source NotebookLM + Obsidian deep dive
  - `readwise-api-triage` → Readwise Reader queue triage and selected-source handoff
  - `readwise-notebooklm-check` → repository development check
  - `readwise-notebooklm-install-skills` → copy this skill into Codex/Claude/Agents homes

Operational rules:

- Prefer the packaged CLI commands over ad-hoc Readwise / NotebookLM shell snippets.
- When workflow behavior needs to change, patch the package first, reinstall it, then update this skill only if the agent-facing instructions changed.
- Use dry-run modes before external mutations or NotebookLM/Obsidian object creation.

## Default Command

Use the local helper first when the user gives a canonical URL:

```bash
readwise-nlm-deepdive "https://example.com/article" \
  --title "Human Title" \
  --type article \
  --why "why studying this now" \
  --domain robotics \
  --domain sim2real \
  --tag readwise \
  --tag notebooklm
```

For papers:

```bash
readwise-nlm-deepdive "https://arxiv.org/pdf/...." \
  --title "Paper Title" \
  --type paper \
  --why "why this matters" \
  --domain robotics \
  --domain sim2real \
  --tag paper-reading
```

Use `--dry-run` to preview without creating NotebookLM objects or writing a note.

## Readwise API Triage

When the user asks to list/filter recent Readwise items, find what to read, or use the Readwise API, prefer:

```bash
readwise-api-triage
```

Common usage:

```bash
readwise-api-triage --days 7 --location new \
  --domain robotics --domain vla --domain sim2real \
  --top 20 --write-obsidian
```

```bash
readwise-api-triage --days 7 --location new \
  --domain robotics --domain vla --domain sim2real \
  --to-nlm <reader-document-id>
```

## NotebookLM / Obsidian Rules

- Prefer canonical/original source URLs over Readwise wrapper pages.
- One article/paper should map to one NotebookLM notebook.
- Source notes should live in the user's configured Obsidian article/source-note area.
- Durable concepts should later be promoted into the relevant engineering/project notes.
- If NotebookLM auth fails, ask the user to run `nlm login`; do not invent a fallback notebook.

## Safety

- Never print Readwise tokens or private Obsidian content.
- Never delete NotebookLM notebooks/sources without explicit confirmation.
- Do not share notebooks publicly unless explicitly asked.
- Use `readwise-api-triage --dry-run` before archive/later operations unless the user explicitly requested the mutation.
