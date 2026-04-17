# AGENTS.md - Readwise NotebookLM Agent

This repository contains CLI helpers for an agent-first Readwise → NotebookLM →
Obsidian reading workflow.

## Mission

Help agents reliably:

1. query Readwise Reader API for recent reading candidates;
2. rank/filter candidates by user-relevant domains;
3. write an Obsidian triage note;
4. create one NotebookLM notebook per selected source;
5. create or update the matching Obsidian source note.

## Key Commands

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --top 20 --write-obsidian
```

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --to-nlm <reader-document-id>
```

```bash
readwise-nlm-deepdive "<canonical-url>" \
  --title "<title>" \
  --type article \
  --why "<reason>"
```


## Readwise backend selection

Default to `--backend auto`. In auto mode the helper uses the official
`readwise` CLI when it is installed and falls back to direct Reader API v3 when
it is not. Use `--backend readwise-cli` only when the official CLI is required;
use `--backend api` for Python-only environments.

Agents should prefer the official CLI for Readwise data access, but keep this
package responsible for domain scoring, NotebookLM handoff, and Obsidian note
creation.

## Agent Defaults

- Use `readwise-api-triage` when the task mentions recent Readwise items,
  reading candidates, triage, queue cleanup, or Reader API.
- Use `readwise-nlm-deepdive` when the user has already selected one article or
  paper and wants a NotebookLM workspace.
- Prefer canonical `source_url` over Readwise wrapper URLs.
- Interpret `--days` as KST-aware local time conversion built into the helper;
  do not manually compute UTC unless the user asks for an explicit window.
- Write durable outputs into the Obsidian vault via `--write-obsidian` or the
  deep-dive helper's source-note scaffold.


## Domain customization

Do not assume every user wants the author's robotics/sim2real domains. The
package defaults are generic. For specialized workflows, ask for or create a
`--domains-file` JSON config. The bundled robotics/VLA/sim2real file under
`examples/` is only a sample; copy and edit it for the current user's interests.

Agents should mention which domain file was used when reporting triage results.

## OpenClaw / Browser Automation

Use OpenClaw or any logged-in browser automation only when:

- the URL is LinkedIn/X/Threads/social and NotebookLM import is likely to fail;
- Readwise only exposes a wrapper URL;
- the canonical link or full text must be extracted from a logged-in page.

Do not use browser automation for public arXiv, GitHub, NVIDIA/OpenAI/Google
blog, Substack, or normal web pages unless import fails.

## Secrets and Privacy

- Never print `READWISE_TOKEN` or the token inside Obsidian plugin config.
- Never commit `.env`, token files, `Readwise/`, or
  `.obsidian/plugins/readwise-official/`.
- Do not expose private Readwise/Obsidian content in GitHub issues, PRs, or logs.

## Mutations

Default to read-only. For any command that changes external state:

- Use `--dry-run` first for `--archive` / `--later`.
- Ask for explicit confirmation before deleting NotebookLM objects.
- Do not share NotebookLM notebooks publicly unless explicitly requested.

## Development Checks

Run before claiming completion:

```bash
python -m compileall src tests
python -m unittest discover -s tests -v
python -m readwise_notebooklm_agent.triage --help >/tmp/triage-help.txt
python -m readwise_notebooklm_agent.deepdive --help >/tmp/deepdive-help.txt
```

## Commit Style

Use conventional commits where possible and include rationale in the body when
behavior changes.

## Environment variables

- `READWISE_NOTEBOOKLM_OBSIDIAN_VAULT`: preferred Obsidian vault path for these tools.
- `OBSIDIAN_VAULT`: backwards-compatible fallback vault path.
- `READWISE_NOTEBOOKLM_DOMAINS_FILE`: optional default domain JSON file so agents do not need to pass `--domains-file` every time.
- `READWISE_TOKEN`: optional Readwise token override; otherwise the tool reads the Obsidian Readwise plugin config.
