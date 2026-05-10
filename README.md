# JARVIS

> "Good morning, sir."

A small, single-user automation that posts a curated daily briefing to Slack every morning. The character voice is intentional — Tony Stark's AI assistant — and confined to user-facing surfaces (Slack output, this README, log lines). Internals are plain Python.

You declare what you care about in two YAML files (`config.yaml` for sources and search themes, `profile.yaml` for your role and priorities). At 07:00 each day, JARVIS pulls the last 24 hours from the sources you named, asks Claude Code to also web-search for the themes you listed, ranks everything against your priorities, and posts a single markdown message to Slack.

## What you'll see

A typical brief is one Slack message, 5–15 entries, grouped by topic. Excerpt:

```
🎩 Good morning, sir.

Here is your briefing for Tuesday, 2026-05-05.

🤖 Humanoid robotics & control

🔥 [Industry] Meta acquires Assured Robot Intelligence — staking out the
   "Android of humanoids" intelligence layer
   Reported May 1. Meta is positioning to own the cross-OEM intelligence
   stack rather than building its own platform — directly reshaping the
   make-vs-buy calculus for whole-body controllers and the platform
   companies you track.
   https://techfastforward.com/articles/...

🏰 Disney parks

📌 [Event · 2026-05-26] Walt Disney World opens seven attractions on the
   same day
   Single mass-opening day at WDW: Rock 'n' Roller Coaster Starring The
   Muppets (Hollywood Studios), Bluey's Wild World (Animal Kingdom),
   Soarin' Across America (EPCOT), and more. Three weeks out — book if
   planning a trip.
   https://mickeyvisit.com/...

That will be all, sir.
```

Full sample: [`samples/example_briefing.md`](samples/example_briefing.md).

`🔥` marks the single highest-priority item of the day (capped at one), `📌` marks notable items (capped at five), plain entries are everything else.

## How it works

```
cron (07:00)                                                     ┌─ Slack
   │                                                             │
   ▼                                                             │
run.sh ──▶ jarvis.fetchers.* ──▶ jarvis.state (dedupe) ──▶ claude -p ──▶ jarvis.deliver
                │                       ▲                    │              │
                │                       │                    │       (strips meta,
                └───── /tmp/raw/*.json ─┘             prompts/daily_brief.md  posts text)
                                                      config.yaml, profile.yaml
                                                      web_search (Claude Code)

                  on success: jarvis.state (mark-delivered) ──▶ state/seen.sqlite
                  (only items whose URL is in the briefing are marked)
```

JARVIS draws from two parallel collection paths and merges them at synthesis time:

- **Deterministic fetchers** read fixed sources named in `config.yaml`. arXiv categories and YouTube channel IDs are queried at the API level, output is normalized to a unified JSON envelope, and the dedupe step filters out items already delivered. Window: `window.hours` (default 24).
- **Heuristic web search** runs at synthesis time, inside the `claude -p` call. The prompt reads `search_themes` from `config.yaml` and uses Claude Code's `web_search` tool to surface fresh content matching those themes. No fetcher code required for new heuristic topics — adding `"BLACKPINK ticketing 2026"` under `search_themes.leisure` is the entire onboarding for that signal. Window: `window.heuristic_hours` (default 168 — concert and theme-park news have weekly cadence, not daily).

The synthesis prompt distinguishes *news-style* items (article publication date matters; drop if missing) from *event-style* items (event date matters — concert ticketing pages, theme-park ride openings). Event-style items are kept even when the page lacks a parseable publication timestamp, and are labelled `[Event · YYYY-MM-DD]` so you can see at a glance when something happens.

`mark-delivered` records only items whose URL actually appears in the delivered brief. Items the synthesis judges off-topic stay unseen — so a later edit to `profile.yaml`'s `priority_keywords` can re-surface them on a future run, instead of losing them silently.

A failed delivery does *not* advance `mark-delivered`. The next run sees the same items as new and gets another chance. Recoverability over double-posting.

### Brief archive and cross-day dedup

On every successful delivery, `run.sh` copies the brief to `state/briefings/<YYYY-MM-DD>.md` (gitignored, one ~3 KB file per day, ~1 MB per year). Two side benefits:

- The synthesis prompt reads the most recent `dedup.recent_briefs_count` archived briefings on each subsequent run, so it can recognise when a `web_search` result describes an event already covered (different URL, same event) and either drop it or surface a `[update]`-prefixed follow-up if there is genuinely new development.
- `jarvis.state export-seen-recent` writes a flat list of URLs delivered within the last `dedup.recent_days` days to `/tmp/raw/seen_recent.txt`; the synthesis prompt treats this as a strict deny-list for `web_search` results, so an exact-URL repeat never makes it back into the brief.

Defaults in `config.yaml.dedup`: `recent_days: 14`, `recent_briefs_count: 14`. The two windows are aligned at fourteen days so cross-day dedup reasons over a single time scale.

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
6. Schedule it. See the next section.

### Schedule it (cron)

`run.sh` writes its own `run.log` and is safe to call from cron. The catch on macOS is that cron starts with an essentially empty `PATH`, so `claude`, `python3`, and friends are not found unless you set `PATH` explicitly inside the crontab.

A working crontab on Apple Silicon macOS:

```cron
PATH=/opt/homebrew/bin:/opt/homebrew/sbin:/usr/bin:/bin

# JARVIS daily briefing — 07:00 local
0 7 * * * /full/absolute/path/to/jarvis/run.sh >/dev/null 2>&1
```

Notes:

- `>/dev/null 2>&1` — `run.sh` already writes to `run.log`. Without the redirect, cron mails you on every run.
- If `claude` was installed via `nvm`, it lives at `~/.nvm/versions/node/<version>/bin/claude` and that path is fragile (a `nvm install <newer>` invalidates it). The robust fix is one symlink:
  ```bash
  ln -sf "$(which claude)" /opt/homebrew/bin/claude
  ```
  Now the crontab `PATH` above is enough.
- macOS may pop up a Full Disk Access prompt the first time cron runs. If it gets dismissed and the run fails silently, add `/usr/sbin/cron` under **System Settings → Privacy & Security → Full Disk Access**.

Verify after the first scheduled run:

```bash
tail -30 run.log
log show --predicate 'process == "cron"' --last 1d
```

### If you forked this repo

The committed `config.yaml` and `profile.yaml` reflect the maintainer's setup, not yours. Before your first run:

- Edit `config.yaml`:
  - `arxiv.categories` — pick the arXiv categories that match your interests (e.g., `cs.LG` instead of `cs.RO`).
  - `youtube.channels` — replace the maintainer's `UC...` channel list with yours. Resolve handles via `https://www.googleapis.com/youtube/v3/channels?forHandle=@<handle>&part=id&key=$YOUTUBE_API_KEY`.
  - `search_themes.career` and `search_themes.leisure` — natural-language phrases, fed straight into Claude Code's `web_search`.
- Edit `profile.yaml`:
  - `role` — one or two sentences on what you do. The synthesis prompt uses this to bias categorization.
  - `priority_keywords` — terms that should boost an item's rank. Mix professional and personal — leisure terms here are what surfaces concert / theme-park signals on the heuristic path.
  - `upcoming_events` — absolute-dated events you want surrounding signal for (concert ticketing windows, conferences, trips).

## Configuration reference

| File / Path                  | Tracked? | Purpose                                                                            |
| ---------------------------- | :------: | ---------------------------------------------------------------------------------- |
| `config.yaml`                |    ✅    | Source list (arXiv, YouTube), search themes, scheduling, lookback windows.         |
| `profile.yaml`               |    ✅    | Your role, priority keywords, upcoming events, output language.                    |
| `prompts/daily_brief.md`     |    ✅    | Synthesis prompt the headless `claude -p` call runs.                               |
| `scripts/init.sh`            |    ✅    | Interactive credential bootstrap — populates `.env`.                               |
| `run.sh`                     |    ✅    | Daily orchestrator — invoked by cron.                                              |
| `.env.example`               |    ✅    | Documented manifest of secrets the init script prompts for.                        |
| `.env`                       |    ❌    | Your real Slack webhook URL and YouTube API key. Populate via `scripts/init.sh`.   |

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

## Troubleshooting

The single source of truth for any failed run is `run.log` in the repo root. `tail -50 run.log` after a missed brief, then match against the patterns below.

**No log entries for the expected time.** cron didn't fire. Verify `crontab -l`; check `log show --predicate 'process == "cron"' --last 1d`. On macOS, the most common cause is missing Full Disk Access for `/usr/sbin/cron`.

**`claude: command not found` or `python3: not found` in the log.** cron's `PATH` is missing the binary's directory. See [Schedule it (cron)](#schedule-it-cron) — set `PATH=` in the crontab, or symlink `claude` into `/opt/homebrew/bin`.

**`STEP delivery done` but no Slack message.** The webhook URL is valid HTTP-wise but points at a revoked / wrong channel. Re-run `bash scripts/init.sh` to re-enter and use the opt-in smoke test to verify the new URL end-to-end.

**`[youtube] HTTP 403 for channel=...`.** YouTube API key is expired or has hit its daily quota. Rotate at the Google Cloud console; re-run `bash scripts/init.sh` to update `.env`.

**`claude synthesis failed`.** The Claude Code CLI session may need re-authentication. Run `claude` interactively once and complete sign-in; cron will pick up the refreshed session.

**Brief shape changes unexpectedly (no leisure section, only arXiv).** `web_search` may not have been authorized in the headless invocation. `run.sh` passes `--allowedTools "WebSearch" "WebFetch"`; if you've forked and modified `run.sh`, that's the first place to check.

**Topic I care about never appears.** Add it to both `config.yaml` (under the right `search_themes` block — natural language phrasing) and `profile.yaml.priority_keywords`. The heuristic branch picks it up at the next run.

## Voice scope

The JARVIS voice ("Good morning, sir." / "That will be all, sir.") appears only on user-facing surfaces:

- Slack message body (driven by the synthesis prompt).
- This README.
- A small set of public function/class names (`dispatch()`, `Briefing`).
- INFO-level log lines (optional).

It does not appear in configuration keys, error messages, internal variable names, or stack traces. Internals are plain English.

## Spec

Requirements live as OpenSpec specs in [`openspec/specs/`](openspec/specs/). Active and archived changes are under [`openspec/changes/`](openspec/changes/) — the v1 bootstrap that established the system is archived as `2026-05-05-bootstrap-jarvis-v1`.

## License

[MIT](LICENSE).
