# CLAUDE.md - Agent Usage Guide

Claude/Codex/OpenClaw agents should treat this repo as a small, reliable tool
surface for Readwise Reader triage and NotebookLM deep dives.

## Fast Path

If asked "Readwise에서 읽을만한 것 뽑아줘":

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --top 20 --write-obsidian
```

If asked to deep-dive one Reader item:

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --to-nlm <reader-document-id>
```

If given a URL directly:

```bash
readwise-nlm-deepdive "<url>" --title "<title>" --type article --why "<reason>"
```


## Domain customization

Do not assume every user wants the author's robotics/sim2real domains. The
package defaults are generic. For specialized workflows, ask for or create a
`--domains-file` JSON config. The bundled robotics/VLA/sim2real file under
`examples/` is only a sample; copy and edit it for the current user's interests.

Agents should mention which domain file was used when reporting triage results.

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

## Environment variables

- `READWISE_NOTEBOOKLM_OBSIDIAN_VAULT`: preferred Obsidian vault path for these tools.
- `OBSIDIAN_VAULT`: backwards-compatible fallback vault path.
- `READWISE_NOTEBOOKLM_DOMAINS_FILE`: optional default domain JSON file so agents do not need to pass `--domains-file` every time.
- `READWISE_TOKEN`: optional Readwise token override; otherwise the tool reads the Obsidian Readwise plugin config.
