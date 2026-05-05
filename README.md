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
                                                      profile.yaml
                                                      web_search (Claude Code)

                              on success: jarvis.state (mark-seen) ──▶ state/seen.sqlite
```

- **Deterministic fetchers** (Python) cover sources where missing items would be a defect: arXiv (`cs.RO` by default) and YouTube channels you list. They emit a unified JSON schema.
- **Heuristic search** is delegated entirely to Claude Code's `web_search` tool, driven from the synthesis prompt. No fetcher code is needed for keyword-shaped sources (event news, market headlines, niche topics).
- **SQLite seen-tracking** filters previously-delivered items out before synthesis, and records new items only after a successful Slack delivery — so a failed run is recoverable.
- **Single LLM call per day** via `claude -p` (Claude Code CLI headless). With a Claude Max subscription, marginal cost ≈ $0.

## Fork & set up

JARVIS is designed to be forked. The repo tracks the maintainer's actual configuration (channel list, search themes, profile) so a fresh clone runs end-to-end as soon as `.env` is populated. Only secrets — Slack webhook URL and YouTube API key — live in a gitignored `.env`.

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
4. Populate `.env` interactively:
   ```bash
   bash scripts/init.sh
   ```
   The script reads `.env.example`, prompts for each variable (with the example file's leading comment shown as help text), masks input for keys that look secret-shaped, writes `.env` with mode 600, and offers an opt-in Slack smoke test that posts a labelled `[JARVIS init]` setup notice via the webhook so a typo is caught at setup time rather than at the next scheduled run.
5. Verify end-to-end manually:
   ```bash
   bash run.sh
   ```
   You should see a Slack message in the channel bound to your webhook.
6. Schedule it. Add the line below to your crontab via `crontab -e`:
   ```
   0 7 * * * /full/absolute/path/to/jarvis/run.sh
   ```

### If you forked this repo

The committed `config.yaml` and `profile.yaml` reflect the maintainer's setup, not yours. Before your first run:

- Edit `config.yaml`:
  - `arxiv.categories` — pick the arXiv categories that match your interests (e.g., `cs.LG` instead of `cs.RO`).
  - `youtube.channels` — replace the maintainer's `UC...` channel list with yours. Resolve handles via `https://www.googleapis.com/youtube/v3/channels?forHandle=@<handle>&part=id&key=$YOUTUBE_API_KEY`.
  - `search_themes.career` and `search_themes.leisure` — phrase these as natural-language queries; they feed Claude Code's `web_search` tool.
- Edit `profile.yaml`:
  - `role` — one or two sentences on what you do, used by the synthesis prompt to bias categorization.
  - `priority_keywords` — terms that should boost an item's rank.
  - `upcoming_events` — absolute-dated events you want surrounding signal for (concert ticketing windows, conferences, trips).

## Configuration reference

| File                            | Tracked? | Purpose                                                              |
| ------------------------------- | :------: | -------------------------------------------------------------------- |
| `config.yaml`                   |    ✅    | Sources, search themes, scheduling, lookback windows.                |
| `profile.yaml`                  |    ✅    | Your role, priority keywords, upcoming events, output language.      |
| `prompts/daily_brief.md`        |    ✅    | Synthesis prompt the headless Claude Code call runs.                 |
| `.env.example`                  |    ✅    | Documented manifest of secrets the init script prompts for.          |
| `.env`                          |    ❌    | Your real Slack webhook URL and YouTube API key. Populate via `scripts/init.sh`. |

## Public-repo safety contract

If you push your fork to a public GitHub repo (or this upstream is mirrored), the rules below are non-negotiable. A leaked secret in git history is cached by GitHub and unreliable to remove with force-push.

The repo ships three independent defenses:

1. **`.gitignore`** covers every secret-bearing and ephemeral path: `.env`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, `/tmp/briefing.md`. `config.yaml` and `profile.yaml` are intentionally tracked — they hold non-secret configuration.
2. **`pre-commit` secret scanner** (`gitleaks`) runs on every commit. Run `pre-commit install` once after cloning so the hook is wired up.
3. **GitHub Push Protection** — enable it in your fork's **Settings → Code security → Push protection** before your first push.

### Pre-first-push checklist

Run before your *first* `git push`:

```bash
git status                       # No .env, state/seen.sqlite, run.log, /tmp/* should appear.
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
