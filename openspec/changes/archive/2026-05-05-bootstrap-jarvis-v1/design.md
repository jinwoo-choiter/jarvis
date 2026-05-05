## Context

JARVIS is a single-user, locally-hosted daily-briefing automation, intended to be forked by individuals who want a curated morning summary of a few topics they care about. It is not a service, not multi-tenant, and not deployed to shared infrastructure.

The framework is designed around four assumptions that hold for the typical fork:

1. The user runs the pipeline on a machine that stays powered (Mac mini, NUC, always-on laptop, home server).
2. The user already has a Claude account and ideally a Claude Max subscription, so the LLM call is `claude -p` (Claude Code CLI headless) rather than a paid API endpoint. Marginal cost per day is effectively zero.
3. The user’s curation preferences (which sources, which keywords, which categories, what their job context is) belong in local-only files. The committed repo is generic.
4. The repo is **public** by default. The fork target is a portfolio-or-OSS asset, so secret leakage and personal-context leakage into git history are unacceptable. This drives the directory layout, the config-layering, and the pre-commit defenses.

This change is the v1 bootstrap. The repository starts essentially empty (only OpenSpec scaffolding exists), so the design pins every cross-cutting decision in one place. Subsequent changes will refine pieces of this design rather than restate it.

## Goals / Non-Goals

**Goals**

- A pipeline that runs once per day, unattended, and posts exactly one curated Slack message.
- Deterministic exhaustive coverage on sources where missing items would be a defect (e.g. all of yesterday’s arXiv `cs.RO` papers, every new video on subscribed YouTube channels).
- Heuristic, keyword-shaped coverage delegated to `web_search` from inside the synthesis prompt — no fetcher code required for those sources.
- A safe-by-default public-repo footprint: any forker who follows the README will not commit their secrets or personal context.
- A character voice (JARVIS) confined to user-facing surfaces, never bleeding into internals.
- A debugging cadence where every step can be run manually and inspected via files on disk.

**Non-Goals**

- Direct scraping of ticketing or theme-park sites (fragile, high-maintenance — `web_search` covers the same ground at lower code cost).
- Delivery channels other than Slack (email, Telegram, Discord, Obsidian vault writes — all deferred).
- Multi-user support, web UI, dashboards, trend analysis.
- Migration to Claude Code Routines (cloud) or Anthropic API direct calls — both kept open as future fallbacks but explicitly out of v1.
- Automated regression testing of `web_search` outputs (non-deterministic by nature).
- A turnkey installer or auto-cron-registration; the user runs `crontab -e` themselves in v1.

## Decisions

### D1. Execution environment: local cron + Claude Code CLI headless

**Decision**: User crontab invokes `run.sh` (typical schedule `0 7 * * *`). `run.sh` runs Python fetchers, dedupes, calls `claude -p`, posts to Slack, and updates state.

**Rationale**:
- Always-on local machine means zero hosting cost.
- A Claude Max subscription absorbs the LLM call via `claude -p`. Single billing channel.
- Local manual reruns of the same command provide the fastest debug loop.
- Claude Code exposes `web_search`, file I/O, and Bash to the synthesis step out of the box.

**Rejected alternatives**:
- **Anthropic API direct call**: ~$6/month additional, splits billing. Kept as a future fallback if Max usage becomes constrained.
- **Claude Code Routines (cloud)**: removes the local debug loop. Kept as a future migration target after the system is stable.
- **Claude Cowork / desktop apps**: require a GUI session to be active. Unsuitable for a cron-driven pipeline.

### D2. Source strategy: deterministic fetchers + heuristic web_search hybrid

**Decision**: Sources where exhaustive coverage matters (arXiv `cs.RO`, subscribed YouTube channels) are fetched by code. Sources where keyword agility matters more than exhaustiveness (event news, market headlines, niche topics) are handled inside the synthesis prompt via `web_search`.

**Rationale**: A search-only approach silently drops items that are not popular enough to surface; a fetcher-only approach forces every new keyword interest into a code change. The split keeps the codebase small while preserving completeness where it matters.

**Rejected alternatives**:
- Direct scraping of event/ticketing sites: HTML changes break scrapers; press coverage is timely enough.
- Per-keyword Google News RSS fetchers: `web_search` does the same work with less code and better composability inside the prompt.

### D3. Delivery channel: Slack incoming webhook

**Decision**: Single Slack incoming webhook, URL stored in `.env` as `SLACK_WEBHOOK_URL`.

**Rationale**: Five-minute setup, no auth tokens, native mobile push, markdown-compatible, automatic link previews. Sufficient for a single-user reading surface.

**Rejected**: Email (SES/SMTP), Telegram bot, Obsidian vault writes — all deferred to v2.

### D4. LLM invocation: `claude -p` with `--add-dir`

**Decision**:
```bash
claude -p "$(cat prompts/daily_brief.md)" --add-dir /tmp/raw > /tmp/briefing.md
```

- `-p` (`--print`) for non-interactive single-shot execution; result on stdout.
- `--add-dir /tmp/raw` exposes fetcher JSON output to the session via the Read tool.
- `web_search` is invoked from within the prompt by natural-language instruction.

This is the standard Claude Code headless flow. Tool permissions are left at defaults in v1; tightening can come later via Claude Code settings.

### D5. User-profile injection: `profile.local.yaml`, never committed

**Decision**: User context (job role, priority keywords, upcoming events) lives in `profile.local.yaml` (gitignored). The committed `profile.example.yaml` is a template only. The synthesis prompt references the profile so a forker’s personal data never enters git history.

**Implementation**: The simplest viable approach in v1 is to expose the profile to the Claude Code session via `--add-dir` (or a parent directory containing it) and instruct the prompt to read it first. Whether to also pre-substitute via shell or Python is left as an implementation detail; the firm constraint is *the profile file is never committed*.

### D6. Deduplication: SQLite seen-tracking, mark-after-deliver

**Decision**: `state/seen.sqlite` with a single table `(url_hash TEXT PRIMARY KEY, first_seen TIMESTAMP, category TEXT)`. After fetchers run, `state.dedupe` writes the new-only subset to `/tmp/raw/new.json`. After a successful Slack POST, `state.mark_seen` records the new URL hashes.

**Rationale**: Determinism belongs in Python where it can be tested. Claude only ever sees items already known to be new, so its job is classification and summarization, not memory.

**Transactional ordering**: `mark_seen` runs *only after* delivery succeeds. A failed run leaves the same items unseen so the next run retries them.

**Trade-off**: items found by `web_search` cannot be deduplicated by URL — the prompt receives no record of past `web_search` output. v1 mitigates with two prompt-side rules: a 24-hour publication filter, and a "merge multiple outlets covering the same event into one entry" instruction. No quantitative dedup is attempted on this path in v1.

### D7. Entry point: `run.sh` (Bash) for v1

**Decision**: `run.sh` is the v1 entry point. Each step writes to a file on disk so the user can `cat` intermediate output during debugging. A Python `orchestrator.py` is kept as a future option but not used in v1.

**Rationale**: For a five-step linear pipeline, Bash is shorter and easier to inspect. Migrating to Python is straightforward when complexity warrants it.

### D8. Public-repo safety contract: three independent defenses

**Decision**:
1. `.gitignore` covers `.env`, `*.local.yaml`, `prompts/*.local.md`, `state/seen.sqlite`, `run.log`, `__pycache__/`, `.venv/`, `/tmp/raw/`, `/tmp/briefing.md`.
2. `.pre-commit-config.yaml` runs a secret scanner on every commit (`gitleaks` is the v1 choice; `detect-secrets` is an acceptable substitute).
3. The README documents enabling **GitHub Push Protection** (Settings → Code security) at fork time, plus a pre-first-push checklist (`git status`, `git diff --cached`, secret-grep).

Config layering is two-tier: `*.example` files (committed, no real values) and `*.local.*` files (gitignored, real values). A forker copies `*.example` → `*.local.*` and edits in place.

**Trade-off**: a forker who wants extra safety can start the fork as a private repo, stabilize for a week, then flip to public. v1 design assumes the contract above is sufficient regardless of which path the forker chooses.

### D9. Directory layout

```
jarvis/
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── LICENSE                              # MIT
├── pyproject.toml
├── .env.example
├── config.yaml                          # safe defaults, source metadata
├── config.local.yaml.example            # forker template
├── profile.example.yaml                 # user-context template
├── samples/example_briefing.md          # anonymized output sample
├── prompts/daily_brief.md               # generic prompt
├── jarvis/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── arxiv.py                     # cs.RO RSS → JSON
│   │   └── youtube.py                   # YouTube Data API v3 → JSON
│   ├── state.py                         # SQLite seen-tracking
│   ├── deliver.py                       # Slack webhook POST
│   └── orchestrator.py                  # optional, unused in v1
├── run.sh                               # cron entry point
├── state/.gitkeep                       # seen.sqlite is gitignored
└── openspec/                            # OpenSpec metadata (already exists)
```

### D10. Unified fetcher output schema

```json
{
  "source": "arxiv | youtube",
  "fetched_at": "<ISO 8601 with timezone>",
  "items": [
    {
      "id": "<source>:<stable-unique-id>",
      "title": "...",
      "url": "https://...",
      "published_at": "<ISO 8601>",
      "summary_raw": "...",
      "metadata": { "<source-specific fields>": "..." }
    }
  ]
}
```

`id` is a stable identifier separate from the URL hash so version-suffixed sources (e.g. arXiv `v2`) still match. URL hash is the dedup key.

### D11. Prompt design contract (`prompts/daily_brief.md`)

The prompt MUST:
1. Inject the user profile (role, priority keywords, upcoming events) so synthesis is contextual.
2. Separate deterministic instructions ("read and categorize `/tmp/raw/*.json`") from heuristic instructions ("`web_search` for the following keyword themes").
3. Inject today’s date and require a 24-hour publication filter; exclude items lacking publication time information.
4. Cap priority markers — at most one 🔥 per day, at most five 📌 per day — to prevent grade inflation.
5. Instruct merging multiple outlets covering the same event into a single item, citing the most primary source.
6. Pin the output format: JARVIS voice for the opener and closer, Korean body text, Slack-compatible markdown, and a source URL on every item.

The prompt is the single largest determinant of output quality. It is committed; the `*.local.md` variant for personal augmentation is gitignored.

### D12. Character voice scope

- **Voice applied**: Slack message body (via prompt instruction), README first line, INFO log lines (optional), a few public function/class names (`dispatch()`, `Briefing`).
- **Voice forbidden**: internal variable names, error tracebacks, debug logs, configuration keys.

The principle: voice on user-facing surfaces, plain English everywhere else.

### D13. Dependencies

- RSS parsing: `feedparser` (concise) or `httpx + xml.etree` (stdlib-leaning). v1 picks **`feedparser`** unless implementation reveals friction.
- YouTube Data API v3: direct HTTP via `httpx`. The official `google-api-python-client` is overkill for one or two endpoints.
- YAML: `pyyaml`.
- HTTP: `httpx`.

New dependencies beyond this set require explicit user agreement before being added.

### D14. Code style

- Python type hints throughout. Small functions with explicit signatures.
- Code, comments, docstrings, identifiers: English. User-facing strings (Slack output, README user-visible sections, INFO log lines): the user’s preferred language (Korean in the project owner’s default profile; configurable per fork).
- Default to no comments. Add a one-liner only when the *why* is non-obvious.

## Risks / Trade-offs

- **[Public-repo secret leak]** → Three independent defenses (D8) plus a pre-first-push manual checklist. Forkers uncomfortable with the risk can start private and flip later.
- **[Claude Max usage pressure]** → v1’s production cadence is one `claude -p` per day, which is well within typical Max limits. The README warns against repeated manual reruns during prompt iteration. Anthropic API fallback is deferred to a future change.
- **[`web_search` non-determinism]** → Acceptable for v1’s heuristic path. Manual stepwise verification covers it; automated tests are scoped to the deterministic components only.
- **[arXiv RSS unavailability]** → Fetchers MUST emit a structurally valid empty result on transient failure so the pipeline does not abort. The prompt handles "no new items in this category" gracefully.
- **[Slack webhook rotation/expiry]** → `deliver.py` exits non-zero on HTTP failure; the orchestrator skips `mark_seen` and surfaces the error in `run.log` for the user to notice.
- **[YouTube API quota exhaustion]** → Default daily quota (10,000 units) covers a small number of channels comfortably. Forkers adding many channels should reassess.
- **[cron environment isolation]** → `run.sh` MUST source `.env` explicitly; cron does not inherit the user’s interactive shell environment.

## Migration Plan

This is a greenfield bootstrap, so there is no migration *from* anything. The forker’s onboarding path is:

1. Fork the repo.
2. (Optional) Flip the fork to private until stable.
3. Copy `*.example` files to `*.local.*` and fill in real values.
4. Run `bash run.sh` manually end-to-end and verify the Slack message.
5. Enable GitHub Push Protection.
6. Inspect `git status` and `git diff --cached` before the first push; grep for any leaked secret-shaped strings.
7. Push. (If staying private, the public flip can come later.)
8. Register cron: `0 7 * * * /full/path/to/run.sh`.

Rollback before first push is just `rm -rf .git`. After a leak makes it to GitHub, the practical recovery is *credential rotation*, not history rewriting — push history is cached, and force-push is unreliable as a remediation.

## Open Questions

- **`pyproject.toml` build backend**: `hatchling` (modern, minimal) vs `setuptools` (universal). Tentatively `hatchling`; either is acceptable.
- **Secret scanner choice**: `gitleaks` vs `detect-secrets`. Tentatively `gitleaks` (lower false-positive rate, smaller config). Either is acceptable.
- **Profile-injection mechanism**: `--add-dir` exposure with prompt-side read instruction (current default) vs shell `envsubst` pre-substitution vs Python pre-render. Decide at implementation time on the simplest working form.
- **Cron auto-registration**: not in v1. A small `install.sh` could be added in v1.x once the manual path is proven; out of scope here.
- **License**: MIT (tentative). The forker is responsible for confirming compatibility with their employer’s OSS policy.
