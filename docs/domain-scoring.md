# Domain Scoring

`readwise-api-triage` ranks Reader documents with transparent keyword-based
domain scoring. This is intentionally simple so agents and humans can inspect,
modify, and improve behavior without sending private reading data to an LLM.

## Defaults are intentionally generic

The package ships only broad built-in domains:

- `general`
- `technical`
- `ai`

They are not meant to represent every user's interests. They exist so the tool
works out of the box, while serious workflows should provide a custom domain
file.

## User-specific domains

Use `--domains-file` to supply your own JSON file:

```bash
readwise-api-triage --days 7 --location new \
  --domains-file examples/domains.robotics-sim2real.sample.json \
  --domain robotics --domain vla --domain sim2real \
  --top 20
```

A domain file has this shape:

```json
{
  "domain-name": {
    "weight": 6,
    "keywords": ["keyword", "another keyword"]
  }
}
```

Custom files are merged on top of built-ins. If the same domain name appears,
the custom definition replaces the built-in definition.

## Sample: robotics / VLA / sim2real

This repo includes one sample domain file based on the original author's local
workflow:

```text
examples/domains.robotics-sim2real.sample.json
```

Treat it as an example, not a universal default. Other users should copy it and
change the domains to match their own reading system.

## Contributing better examples

Good domain examples are:

- specific enough to separate useful documents from broad noise;
- transparent enough for an agent to explain why an item ranked highly;
- privacy-preserving: no external LLM or embedding API calls by default;
- documented as examples, not hidden personal defaults.

Useful contributions:

- add an example file for a new domain family;
- improve a sample's keyword coverage;
- reduce false positives by removing overly broad terms;
- add tests for custom domain loading.

## Why no embeddings by default?

Readwise summaries and notes can be private. Keyword scoring keeps triage local,
fast, inspectable, and free. A future optional reranker can be added, but it
should be opt-in and clearly document what data leaves the machine.
