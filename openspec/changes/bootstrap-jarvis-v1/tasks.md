## 1. Repository scaffold

- [x] 1.1 Create the directory layout: `jarvis/`, `jarvis/fetchers/`, `prompts/`, `samples/`, `state/` (with `.gitkeep`)
- [x] 1.2 Add `pyproject.toml` with Python version requirement, runtime dependencies (`feedparser`, `httpx`, `pyyaml`), and a build backend
- [x] 1.3 Add `LICENSE` (MIT) at the repo root
- [x] 1.4 Add `README.md` skeleton with: one-line project description in JARVIS voice, "what it does" section, "fork & set up" section (placeholder for the safety checklist), and the cron-registration snippet
- [x] 1.5 Add `.env.example` listing variable names only (`SLACK_WEBHOOK_URL=`, `YOUTUBE_API_KEY=`)
- [x] 1.6 Add `config.yaml` with safe non-sensitive defaults (e.g. arXiv category list = `["cs.RO"]`, empty channel list, default schedule note)
- [x] 1.7 Add `config.local.yaml.example` documenting where the user fills in real channel IDs and any keyword themes
- [x] 1.8 Add `profile.example.yaml` documenting the user-context fields (role, priority keywords, upcoming events) with placeholder values
- [x] 1.9 Add `prompts/daily_brief.md` placeholder with section headers only (filled in task group 5)
- [x] 1.10 Add `samples/example_briefing.md` placeholder (filled in task group 9)

## 2. Public-repo safety contract

- [x] 2.1 Author `.gitignore` covering `.env`, `*.local.yaml`, `prompts/*.local.md`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, `/tmp/briefing.md`
- [x] 2.2 Author `.pre-commit-config.yaml` with the chosen secret scanner (`gitleaks` per design D8; substitute `detect-secrets` if `gitleaks` proves friction during install)
- [x] 2.3 Verify `pre-commit install` succeeds in a fresh clone and that staging a known-bad-shaped string is blocked by the hook
- [x] 2.4 Add the safety section to `README.md`: pre-commit install command, GitHub Push Protection enablement steps, and the pre-first-push checklist (`git status`, `git diff --cached`, secret grep)

## 3. Deterministic fetcher: arXiv cs.RO

- [x] 3.1 Implement `jarvis/fetchers/arxiv.py` reading the category list from `config.local.yaml` (with fallback to `config.yaml`)
- [x] 3.2 Fetch the arXiv RSS for each configured category and parse entries into the unified schema (`source`, `fetched_at`, `items[]`)
- [x] 3.3 Apply the 24-hour publication-window filter; document the timestamp source and timezone in a one-line module docstring
- [x] 3.4 Make the module runnable as `python -m jarvis.fetchers.arxiv`, emitting JSON on stdout
- [x] 3.5 On transient failure (timeout, HTTP 5xx, malformed feed), emit `{"source": "arxiv", "fetched_at": "...", "items": []}` on stdout, log to stderr, exit zero
- [x] 3.6 Manually run `python -m jarvis.fetchers.arxiv | jq` and verify shape

## 4. Deterministic fetcher: YouTube

- [x] 4.1 Implement `jarvis/fetchers/youtube.py` reading the channel ID list from `config.local.yaml`
- [x] 4.2 Authenticate via `YOUTUBE_API_KEY` from the environment; fail fast with a clear stderr message if missing
- [x] 4.3 Enumerate each configured channel's recent uploads via the YouTube Data API v3 and emit items in the unified schema (24-hour window)
- [x] 4.4 Make the module runnable as `python -m jarvis.fetchers.youtube`, JSON on stdout
- [x] 4.5 Apply the same transient-failure contract as arXiv (empty items array, exit zero, stderr diagnostic)
- [ ] 4.6 Manually run with one or two real channel IDs in `config.local.yaml` and verify shape *(needs user — real `YOUTUBE_API_KEY` and channel IDs)*

## 5. Synthesis prompt

- [x] 5.1 Draft `prompts/daily_brief.md` with: opener (instruct JARVIS-voice "Good morning, sir." line), profile-read instruction, today's-date placeholder, deterministic-input section ("read `/tmp/raw/*.json` and categorize"), `web_search` section ("for these keyword themes …"), 24-hour filter rule, priority-cap rules, dedup-merge rule, output-format pin (Slack-markdown body + JARVIS-voice closer), source-URL discipline
- [x] 5.2 Add separation markers/headers so the deterministic and `web_search` blocks are clearly distinguishable
- [x] 5.3 Define how the prompt references `profile.local.yaml` (path it expects, what fields it reads)
- [ ] 5.4 Manually invoke once with a small `/tmp/raw/` populated from the arXiv fetcher: `claude -p "$(cat prompts/daily_brief.md)" --add-dir /tmp/raw > /tmp/briefing.md`; review output by hand *(needs user — costs Max usage; user should run after `.env`/`*.local.*` are in place)*
- [ ] 5.5 Iterate the prompt based on manual-review findings (priority cap behavior, voice consistency, source-URL discipline) *(blocked on 5.4)*

## 6. Slack delivery

- [x] 6.1 Implement `jarvis/deliver.py`: read `SLACK_WEBHOOK_URL` from env, accept the briefing path or stdin, POST as Slack incoming webhook payload
- [x] 6.2 On missing env var, exit non-zero with stderr message naming the variable
- [x] 6.3 On non-2xx response, exit non-zero with stderr including status code and response body
- [x] 6.4 On success, exit zero with a one-line stdout confirmation (suppressible)
- [ ] 6.5 Manually post a hand-written test briefing to verify the channel formatting *(needs user — real `SLACK_WEBHOOK_URL`)*

## 7. Seen-tracking

- [x] 7.1 Implement `jarvis/state.py` with: `init_db()` (creates `state/seen.sqlite` with the schema in design D6), `dedupe(items)` (returns the new-only subset), `mark_seen(items)` (inserts), and a stable URL-hash function
- [x] 7.2 Provide CLI subcommands or module entry points so `run.sh` can call dedupe and mark-seen as discrete steps that read/write JSON on stdin/stdout
- [x] 7.3 Confirm that running dedupe twice with the same input returns the full set then the empty set (after a mark-seen between them)
- [x] 7.4 Confirm that a mark-seen failure leaves the DB unchanged (transaction rollback) — at minimum, that mark-seen is invoked only after delivery success

## 8. Orchestrator: run.sh

- [x] 8.1 Author `run.sh` that: sources `.env`, creates `/tmp/raw/`, runs each configured fetcher into `/tmp/raw/<source>.json`, runs dedupe to produce `/tmp/raw/new.json`, calls `claude -p` with `--add-dir /tmp/raw` redirecting stdout to `/tmp/briefing.md`, calls `jarvis.deliver` against `/tmp/briefing.md`, then on delivery success calls `jarvis.state` mark-seen against `/tmp/raw/new.json`
- [x] 8.2 Implement step-level failure isolation (`set -e` plus per-step `||` guards) so any failure skips mark-seen
- [x] 8.3 Append timestamped log lines for each step start/end and any failure detail to `run.log`
- [x] 8.4 Prefer `prompts/daily_brief.local.md` over `prompts/daily_brief.md` if the local variant exists
- [ ] 8.5 Manually run `bash run.sh` end-to-end and confirm the Slack message arrives *(needs user — real `.env`, `config.local.yaml`, `profile.local.yaml`)*

## 9. Sample output and README polish

- [ ] 9.1 Capture one real briefing, anonymize any user-specific content, and save as `samples/example_briefing.md` *(needs user — depends on 8.5)*
- [x] 9.2 Flesh out `README.md`: project pitch in JARVIS voice, architecture diagram or ASCII flow, fork-and-setup instructions, configuration reference, the safety contract section (from task 2.4), and the cron-registration snippet
- [x] 9.3 Cross-link `openspec/specs/` from the README so future contributors find the requirements

## 10. Pre-first-push verification

- [ ] 10.1 Run `bash run.sh` once more and confirm Slack delivery succeeds end-to-end *(needs user)*
- [ ] 10.2 Run `git status` and verify no `*.local.*`, `.env`, `state/seen.sqlite`, `run.log`, or `/tmp/*` paths are listed *(needs user — pre-push step)*
- [ ] 10.3 Run `git diff --cached` and grep for credential-shaped patterns (Slack webhook prefix, API key prefixes) *(needs user — pre-push step)*
- [ ] 10.4 Enable GitHub Push Protection on the remote repository *(needs user — GitHub UI step)*
- [ ] 10.5 Push (or, if starting private, push to private remote and document the public-flip plan) *(needs user)*

## 11. Cron registration

- [ ] 11.1 Add the cron line via `crontab -e`: `0 7 * * * /full/absolute/path/to/run.sh` *(needs user)*
- [ ] 11.2 Verify `run.log` shows a successful run on the next morning *(needs user — next-day verification)*
- [ ] 11.3 Confirm the Slack channel received the briefing at the scheduled time *(needs user — next-day verification)*
