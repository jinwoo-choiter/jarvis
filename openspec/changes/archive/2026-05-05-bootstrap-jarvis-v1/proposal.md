## Why

People who want to stay current on a few specific topics (their professional field, plus a handful of personal interests) typically pay a daily tax: opening five or ten different sources, skimming, and discarding most of it. A general-purpose news aggregator over-delivers; manual curation under-scales.

JARVIS is a forkable, single-user automation that closes that gap: every morning, a small pipeline gathers raw items from sources the user opted into, hands them to a Claude Code CLI session for synthesis and summarization, and posts a single curated briefing to Slack. The character concept — Tony Stark’s AI assistant — is intentional: the surface (Slack, README, log lines) speaks in that voice, while the internals stay plain.

This change establishes the v1 system end-to-end: the directory layout, the public-repo safety contract that lets others fork without leaking their own secrets, the deterministic fetcher path, the heuristic `web_search` path, the dedup store, the synthesis prompt contract, the Slack delivery, and the cron-driven orchestrator. v1 ships with two reference fetchers (arXiv `cs.RO` RSS and YouTube Data API v3) so a forker has a working baseline; categories, keywords, and source choices are entirely user-configurable through local-only files.

A core design constraint is "marginal cost ≈ $0 for a Claude Max subscriber": the LLM call is `claude -p` headless, not the Anthropic API, so the existing Max plan absorbs it.

## What Changes

- **NEW**: A v1 daily-briefing pipeline that runs once per day on a local machine: `cron → run.sh → Python fetchers → claude -p → Slack incoming webhook`.
- **NEW**: Two reference deterministic fetchers — arXiv `cs.RO` RSS and YouTube Data API v3 — emitting a unified JSON schema. Treat them as starter implementations; forkers can add or replace fetchers without touching the rest of the pipeline.
- **NEW**: A heuristic-search path delegated to Claude Code's `web_search` tool, driven entirely from the synthesis prompt. No additional fetcher code is required for keyword-shaped sources (e.g. event news, market headlines).
- **NEW**: SQLite-backed seen-tracking (`state/seen.sqlite`) that filters previously-delivered items out of fetcher output before synthesis, and records new items only after a successful Slack delivery.
- **NEW**: A synthesis prompt contract (`prompts/daily_brief.md`) that injects the user profile, separates deterministic-vs-heuristic instructions, enforces a 24-hour time filter, caps priority markers to prevent inflation, requires source URLs, and pins the JARVIS voice and Slack-compatible markdown output.
- **NEW**: A two-layer config convention — `*.example` files are committed and act as templates; `*.local.*` files (`.env`, `config.local.yaml`, `profile.local.yaml`, optional `prompts/daily_brief.local.md`) are gitignored and hold the user’s real values. This is what makes the repo safely forkable.
- **NEW**: A public-repo safety contract with three independent defenses: `.gitignore` covering all secret-bearing paths; a `pre-commit` hook running a secret scanner (`gitleaks` or equivalent); and GitHub Push Protection enabled at the repository level. A pre-first-push checklist is included in the README.
- **NEW**: A character/tone guide that scopes JARVIS voice to user-facing surfaces only (Slack output, README, optional log INFO lines, a small set of public function names) and keeps internals plain.
- **EXPLICIT NON-GOALS for v1**: direct scraping of ticketing/theme-park sites; delivery channels other than Slack; writing into an Obsidian vault; multi-user support; web UI/dashboard; trend analysis; non-Korean/non-English output beyond what the prompt template demonstrates; migration to Claude Code Routines; Anthropic API direct-call fallback. All are deferred to a future change.

## Capabilities

### New Capabilities

- `repo-bootstrap`: Project scaffold and the public-repo safety contract — directory layout, `pyproject.toml`, README/LICENSE, the `*.example` ↔ `*.local.*` config split, `.gitignore`, `.pre-commit-config.yaml` with a secret scanner, and the pre-first-push checklist.
- `content-fetching`: Deterministic source fetchers that emit items in a unified JSON schema for downstream consumption. v1 ships arXiv `cs.RO` RSS and YouTube Data API v3 as reference implementations; the capability defines the schema and contract that any future fetcher must satisfy.
- `seen-tracking`: SQLite-backed deduplication that filters fetcher output to new items only and records delivered items, with a transactional ordering that keeps unsent items recoverable on the next run.
- `briefing-synthesis`: The `prompts/daily_brief.md` contract and the `claude -p` headless invocation convention. Covers user-profile injection, the deterministic-vs-`web_search` split, the time filter, the priority cap, source-URL discipline, and the JARVIS-voice Slack-markdown output format.
- `slack-delivery`: Posting the synthesized markdown briefing to a Slack incoming webhook, with explicit failure modes that allow the orchestrator to skip the seen-tracking write.
- `pipeline-orchestration`: The `run.sh` entry point that sequences fetchers → dedupe → synthesis → delivery → mark-seen, plus the cron-registration convention (`0 7 * * *` by default) and operational logging.

### Modified Capabilities

(First change in this repository — none.)

## Impact

- **New code tree**: `jarvis/` (Python package with `fetchers/`, `state.py`, `deliver.py`, optional `orchestrator.py`), `prompts/`, `samples/`, `state/`, `run.sh`.
- **New root config files**: `.gitignore`, `.pre-commit-config.yaml`, `pyproject.toml`, `.env.example`, `config.yaml`, `config.local.yaml.example`, `profile.example.yaml`, `README.md`, `LICENSE`.
- **External dependencies**: a small set of Python packages for RSS parsing, HTTP, and YAML. Exact choices are pinned in design.md and locked at implementation time.
- **External services / accounts** required by a forker to run the system: a Slack incoming webhook URL, a YouTube Data API v3 key, and a Claude Code CLI logged into a Claude account (Max plan recommended for zero marginal cost). All credentials live in `.env` only.
- **Deployment surface**: a single user’s crontab on a machine that stays powered (typically a desktop, mini PC, or always-on laptop). No CI, no remote infrastructure.
- **Risks**: (1) Public-repo secret leak on first push if Push Protection is not enabled in time. (2) Claude Max usage pressure during prompt iteration — mitigated by a one-call-per-day production cadence and explicit guidance to limit manual reruns. (3) `web_search` non-determinism makes regression testing of the heuristic path infeasible — mitigated by manual stepwise verification and by keeping automated tests on the deterministic components only.
