# Readwise NotebookLM Agent

Agent-first CLI helpers for turning a messy Readwise Reader queue into a
source-grounded NotebookLM + Obsidian study workflow.

The default workflow is:

```text
Readwise Reader API
  → score recent reading candidates
  → write an Obsidian triage note
  → create one NotebookLM notebook per selected source
  → create one Obsidian source note per selected source
```

This is designed for users who prefer **one article or paper = one NotebookLM
notebook** for deep focused study.

## What is included

| Command | Purpose |
| --- | --- |
| `readwise-api-triage` | Query Readwise Reader API v3, rank recent documents by domain relevance, write triage notes, and hand selected Reader items to NotebookLM. |
| `readwise-nlm-deepdive` | Create a NotebookLM notebook from one canonical URL, add a Study Brief source, create an `nlm` alias, and scaffold an Obsidian source note. |

Both scripts are Python standard-library only. The NotebookLM command expects
[`notebooklm-mcp-cli`](https://github.com/jacob-bd/notebooklm-mcp-cli) to provide
`nlm`.

## Install

### Recommended: install as a uv tool from GitHub

```bash
uv tool install git+https://github.com/yujeongdev/readwise-notebooklm-agent.git
```

Upgrade later:

```bash
uv tool upgrade readwise-notebooklm-agent
```

### Local editable install

```bash
git clone https://github.com/yujeongdev/readwise-notebooklm-agent.git
cd readwise-notebooklm-agent
uv tool install --editable .
```

Or without uv:

```bash
python -m pip install --user git+https://github.com/yujeongdev/readwise-notebooklm-agent.git
```

## Prerequisites

### 1. Official Readwise CLI (recommended)

Install the official CLI when possible:

```bash
npm install -g @readwise/cli
readwise login
# or for headless setup:
readwise login-with-token <your-access-token>
```

For safer agent use, consider read-only mode in the official CLI:

```bash
readwise config set readonly true
readwise --refresh
```

`readwise-api-triage` defaults to `--backend auto`, which uses the official
`readwise` CLI when it is available on `PATH`, and falls back to direct Reader
API v3 otherwise.

### 2. Readwise token

`readwise-api-triage` reads credentials in this order:

1. `READWISE_TOKEN` environment variable.
2. Obsidian Readwise plugin config at:

   ```text
   $OBSIDIAN_VAULT/.obsidian/plugins/readwise-official/data.json
   ```

Never print this token in agent logs or public output.

### 3. Obsidian vault path

Set this if your vault is not at `~/workspaces/obsidian`:

```bash
export READWISE_NOTEBOOKLM_OBSIDIAN_VAULT="$HOME/workspaces/obsidian"
# OBSIDIAN_VAULT is also supported as a fallback.
```

### 4. NotebookLM CLI

Install and authenticate `nlm`:

```bash
uv tool install notebooklm-mcp-cli
nlm login
nlm login --check
```

Optional but recommended:

```bash
nlm config set auth.browser chrome
```

## Environment variables

```bash
export READWISE_NOTEBOOKLM_OBSIDIAN_VAULT="$HOME/workspaces/obsidian"
export READWISE_NOTEBOOKLM_DOMAINS_FILE="$HOME/.config/readwise-notebooklm-agent/domains.json"
# Optional token override. If omitted, the tool reads the Obsidian Readwise plugin config.
export READWISE_TOKEN="..."
```

`OBSIDIAN_VAULT` is also supported as a backwards-compatible fallback, but
`READWISE_NOTEBOOKLM_OBSIDIAN_VAULT` is preferred for this tool.


## Backend selection

```bash
readwise-api-triage --backend auto         # default: official readwise CLI if present, else API
readwise-api-triage --backend readwise-cli # require official readwise CLI
readwise-api-triage --backend api          # force direct Reader API v3
```

Environment default:

```bash
export READWISE_NOTEBOOKLM_BACKEND=auto
```

Use `readwise-cli` when you want the official CLI to own auth/cache/API
compatibility. Use `api` when running in a minimal Python-only environment.

## Quick start

### List recent Reader candidates

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --top 20
```

### Write an Obsidian triage note

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --top 20 --write-obsidian
```

The note is written to:

```text
$OBSIDIAN_VAULT/900_Articles/Article Inbox/Readwise API Triage - YYYY-MM-DD.md
```

### Send one Reader item to NotebookLM

Copy the `id` from the triage output, then run:

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --to-nlm <reader-document-id>
```

This calls `readwise-nlm-deepdive` with the Reader document's `source_url`.

### Create a NotebookLM deep dive directly from a URL

```bash
readwise-nlm-deepdive "https://arxiv.org/pdf/2512.05107" \
  --title "STARE-VLA" \
  --type paper \
  --why "VLA fine-tuning with stage-aware RL" \
  --domain robotics \
  --domain vla \
  --domain sim2real \
  --tag readwise \
  --tag notebooklm
```

Preview first without creating NotebookLM objects:

```bash
readwise-nlm-deepdive "https://example.com/article" --title "Example" --dry-run
```


## Custom domain scoring

The package defaults are intentionally generic (`general`, `technical`, `ai`).
Most users should provide their own domain file instead of relying on the
author's interests.

A sample robotics/VLA/sim2real config is included at:

```text
examples/domains.robotics-sim2real.sample.json
```

Copy it and edit it for your own reading domains:

```bash
cp examples/domains.robotics-sim2real.sample.json ~/.config/readwise-notebooklm-agent/domains.json
```

Then use it:

```bash
readwise-api-triage --days 7 --location new \
  --domains-file ~/.config/readwise-notebooklm-agent/domains.json \
  --domain <your-domain> --top 20
```

See [`docs/domain-scoring.md`](docs/domain-scoring.md) for the JSON shape and
contribution guidelines.

## Agent operating model

Use the tools like this:

```text
User: "Readwise에서 이번 주 읽을만한 것 뽑아줘"
Agent: readwise-api-triage --days 7 --location new --domain ... --write-obsidian

User: "이 항목 NotebookLM으로 deep dive 세팅해줘"
Agent: readwise-api-triage --to-nlm <reader-document-id>

User gives a clean public URL directly
Agent: readwise-nlm-deepdive <url> --title ... --type article|paper
```

Prefer the Reader API for freshness. Treat the Obsidian Readwise plugin export
as raw archive/highlight sync, not as the source of truth for recent triage.

## OpenClaw / browser automation rule

Use browser/session automation only when needed:

- LinkedIn/X/Threads/social pages fail NotebookLM URL import.
- A Readwise item points to a wrapper URL and the canonical URL must be extracted.
- Logged-in browser state is required to access the source.

Do **not** use browser automation for public arXiv, GitHub, or normal blog URLs.
Send those directly to `readwise-nlm-deepdive`.

## Readwise state mutations

The triage command is read-only by default. State-changing operations are only
performed when explicitly requested:

```bash
readwise-api-triage --archive <reader-document-id> --dry-run
readwise-api-triage --later <reader-document-id> --dry-run
```

Remove `--dry-run` only after the user clearly wants the mutation.

## Safety notes for agents

- Do not print Readwise tokens.
- Do not expose private Readwise or Obsidian content publicly.
- Do not delete NotebookLM notebooks/sources without explicit confirmation.
- Use `--dry-run` for any action that writes outside the local Obsidian vault or
  mutates Readwise state.
- Keep `Readwise/` and `.obsidian/plugins/readwise-official/` out of git.

## Development

This repo is dependency-light and includes a `uv.lock` so agents can use a
consistent Python workflow without guessing tool setup.

```bash
uv run --with-editable . readwise-notebooklm-check
```

Plain Python also works because the package has no runtime dependencies:

```bash
python -m compileall src tests
PYTHONPATH=src python -m unittest discover -s tests -v
```
