# Readwise CLI Backend Plan

## Goal

Prefer the official `readwise` CLI for Readwise/Reader data access while keeping
the direct Reader API as a fallback. This repo should focus on agent workflow:
triage, domain scoring, NotebookLM handoff, and Obsidian notes.

## Why

The official CLI owns:

- auth and token storage;
- Reader document listing/search/detail operations;
- state changes such as archive/later;
- future compatibility with Readwise API changes.

This package owns:

- domain scoring;
- agent-safe defaults;
- Obsidian triage notes;
- one-source NotebookLM notebook creation.

## Backend selection

Add `--backend`:

```text
auto          use official readwise CLI when available, otherwise API
readwise-cli  require official readwise CLI
api           force direct Reader API v3
```

Environment variable:

```bash
export READWISE_NOTEBOOKLM_BACKEND=auto
```

## Implementation shape

Create `src/readwise_notebooklm_agent/readwise_backend.py`:

```python
class BackendError(Exception): ...
class ReadwiseBackend(Protocol):
    list_documents(...)
    update_documents(...)

class ReaderApiBackend:
    # wraps current urllib API functions

class ReadwiseCliBackend:
    # wraps `readwise ... --json` where available
```

The CLI backend should parse JSON only when the official CLI supports JSON for a
command. If the installed CLI lacks a required JSON output, fail clearly and let
`auto` fall back to the API backend.

## First PR scope

1. Add backend abstraction and `api` backend without behavior change.
2. Add `--backend` and `READWISE_NOTEBOOKLM_BACKEND`.
3. Detect `readwise` CLI in `auto` mode.
4. Implement CLI calls conservatively for list/update if JSON output is available.
5. Document official CLI install and readonly recommendation.

## Safety

- Keep read-only triage as default.
- Preserve `--dry-run` for archive/later.
- Do not shell-inject user IDs or queries; pass argv lists to `subprocess.run`.
- Do not print tokens.
