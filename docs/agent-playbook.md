# Agent Playbook

## Decision Tree

```text
Need recent Readwise candidates?
  → readwise-api-triage --write-obsidian

Have a selected Reader document id?
  → readwise-api-triage --to-nlm <id>

Have a selected public URL?
  → readwise-nlm-deepdive <url>

Social/login URL or import failed?
  → use browser/OpenClaw to extract canonical URL or text fallback
```

## Domain presets

Robotics default:

```bash
--domain robotics --domain vla --domain sim2real --domain rl
```

Agent-workflow default:

```bash
--domain agents --domain infra
```

Career default:

```bash
--domain career --domain agents
```

## Domain customization

Do not assume every user wants the author's robotics/sim2real domains. The
package defaults are generic. For specialized workflows, ask for or create a
`--domains-file` JSON config. The bundled robotics/VLA/sim2real file under
`examples/` is only a sample; copy and edit it for the current user's interests.

Agents should mention which domain file was used when reporting triage results.

## Readwise backend selection

Default to `--backend auto`. In auto mode the helper uses the official
`readwise` CLI when it is installed and falls back to direct Reader API v3 when
it is not. Use `--backend readwise-cli` only when the official CLI is required;
use `--backend api` for Python-only environments.

Agents should prefer the official CLI for Readwise data access, but keep this
package responsible for domain scoring, NotebookLM handoff, and Obsidian note
creation.
