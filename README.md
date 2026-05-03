# JARVIS

> "Good morning, sir."

A small, single-user automation that posts a curated daily briefing to Slack every morning.

You point JARVIS at the sources you care about (arXiv categories, YouTube channels, and free-form keyword themes for `web_search`); it pulls the previous 24 hours, hands the result to a Claude Code CLI session for synthesis and summarization, and posts a single Slack message. The character voice is intentional — Tony Stark's AI assistant — and confined to user-facing surfaces (Slack output, this README, log lines). Internals are plain Python.

## What it does

```
cron (07:00)                                                     ┌─ Slack
   │                                                             │
   ▼                                                             │
run.sh ──▶ jarvis.fetchers.* ──▶ jarvis.state (dedupe) ──▶ claude -p ──▶ jarvis.deliver
                │                       ▲                    │
                │                       │                    │
                └───── /tmp/raw/*.json ─┘             prompts/daily_brief.md
                                                      profile.local.yaml
                                                      web_search (Claude Code)

                              on success: jarvis.state (mark-seen) ──▶ state/seen.sqlite
```

- **Deterministic fetchers** (Python) cover sources where missing items would be a defect: arXiv (`cs.RO` by default) and YouTube channels you list. They emit a unified JSON schema.
- **Heuristic search** is delegated entirely to Claude Code's `web_search` tool, driven from the synthesis prompt. No fetcher code is needed for keyword-shaped sources (event news, market headlines, niche topics).
- **SQLite seen-tracking** filters previously-delivered items out before synthesis, and records new items only after a successful Slack delivery — so a failed run is recoverable.
- **Single LLM call per day** via `claude -p` (Claude Code CLI headless). With a Claude Max subscription, marginal cost ≈ $0.

## Fork & set up

JARVIS is designed to be forked. The committed repo contains no real secrets, no real channel IDs, and no personal context — every user-specific value lives in `*.local.*` files that are gitignored.

### Prerequisites

- A machine that stays powered on (Mac mini, NUC, always-on laptop, home server).
- Python 3.11+.
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview) installed and signed in. A Claude Max subscription is recommended so the daily synthesis call has zero marginal cost.
- A Slack workspace where you can [create an incoming webhook](https://api.slack.com/messaging/webhooks).
- A [YouTube Data API v3 key](https://developers.google.com/youtube/registering_an_application) if you want the YouTube fetcher.

### Set-up steps

1. Fork the repo. (Optional but recommended: keep your fork private until you've stabilized it, then flip to public.)
2. Clone your fork and create a virtualenv:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. Install the pre-commit hooks:
   ```bash
   pre-commit install
   ```
4. Copy the templates and fill in real values:
   ```bash
   cp .env.example .env
   cp config.local.yaml.example config.local.yaml
   cp profile.example.yaml profile.local.yaml
   ```
   - `.env`: your Slack webhook URL and YouTube API key.
   - `config.local.yaml`: arXiv categories, YouTube channel IDs, and `web_search` keyword themes.
   - `profile.local.yaml`: your role, priority keywords, and upcoming events. The synthesis prompt reads this so it can bias categorization toward what you care about.
5. Optionally write a personal augmentation for the synthesis prompt at `prompts/daily_brief.local.md` (also gitignored). When present, the orchestrator prefers the local variant.
6. Verify end-to-end manually:
   ```bash
   bash run.sh
   ```
   You should see a Slack message in the channel bound to your webhook.
7. Schedule it. Add the line below to your crontab via `crontab -e`:
   ```
   0 7 * * * /full/absolute/path/to/jarvis/run.sh
   ```

## Configuration reference

| File                            | Committed? | Purpose                                                              |
| ------------------------------- | :--------: | -------------------------------------------------------------------- |
| `config.yaml`                   |     ✅     | Safe defaults (e.g. `cs.RO` only).                                   |
| `config.local.yaml.example`     |     ✅     | Template a forker copies.                                            |
| `config.local.yaml`             |     ❌     | Your real source list. Overrides `config.yaml` per-key.              |
| `profile.example.yaml`          |     ✅     | Template for the user-context profile.                               |
| `profile.local.yaml`            |     ❌     | Your real role, priority keywords, upcoming events.                  |
| `prompts/daily_brief.md`        |     ✅     | Generic synthesis prompt.                                            |
| `prompts/daily_brief.local.md`  |     ❌     | Optional personal augmentation. When present, used in place of the committed prompt. |
| `.env.example`                  |     ✅     | Variable names only.                                                 |
| `.env`                          |     ❌     | Your real Slack webhook URL and YouTube API key.                     |

## Public-repo safety contract

If you push your fork to a public GitHub repo (or this upstream is mirrored), the rules below are non-negotiable. A leaked secret in git history is cached by GitHub and unreliable to remove with force-push.

The repo ships three independent defenses:

1. **`.gitignore`** covers every secret-bearing and ephemeral path: `.env`, `*.local.yaml`, `prompts/*.local.md`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, `/tmp/briefing.md`.
2. **`pre-commit` secret scanner** (`gitleaks`) runs on every commit. Run `pre-commit install` once after cloning so the hook is wired up.
3. **GitHub Push Protection** — enable it in your fork's **Settings → Code security → Push protection** before your first push.

### Pre-first-push checklist

Run before your *first* `git push`:

```bash
git status                       # No *.local.*, .env, state/seen.sqlite, run.log, /tmp/* should appear.
git diff --cached                # Skim every line.
git diff --cached | grep -Ei 'hooks\.slack\.com|AIza|sk-ant-|ghp_|sk-|xox[baprs]-'
                                 # Should produce zero matches.
```

If anything suspicious surfaces, **rotate the credential**, do not just amend the commit — once pushed, recovery is rotation, not history rewriting.

## Voice scope

The JARVIS voice ("Good morning, sir." / "That will be all, sir.") appears only on user-facing surfaces:

- Slack message body (driven by the synthesis prompt).
- This README.
- A small set of public function/class names (`dispatch()`, `Briefing`).
- INFO-level log lines (optional).

It does not appear in configuration keys, error messages, internal variable names, or stack traces. Internals are plain English.

## Spec

Requirements live as OpenSpec specs in [`openspec/specs/`](openspec/specs/). The v1 bootstrap change that established the system is at [`openspec/changes/bootstrap-jarvis-v1/`](openspec/changes/bootstrap-jarvis-v1/).

## License

[MIT](LICENSE).
