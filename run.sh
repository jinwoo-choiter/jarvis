#!/usr/bin/env bash
#
# JARVIS daily-briefing entry point.
# Invoked by cron and by hand for manual verification.
#
#   $ bash run.sh
#
# Required setup (see README):
#   - .env with SLACK_WEBHOOK_URL and YOUTUBE_API_KEY
#   - config.yaml with arXiv categories, YouTube channel IDs, search themes
#   - profile.yaml with the user-context profile
#   - Claude Code CLI installed and signed in (`claude` on PATH)
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

LOG_FILE="$REPO_ROOT/run.log"
RAW_DIR="/tmp/raw"
BRIEFING_FILE="/tmp/briefing.md"
ARCHIVE_DIR="$REPO_ROOT/state/briefings"
PROMPT_FILE="$REPO_ROOT/prompts/daily_brief.md"
PROMPT_LOCAL="$REPO_ROOT/prompts/daily_brief.local.md"

# ---- helpers --------------------------------------------------------------

ts() { date "+%Y-%m-%dT%H:%M:%S%z"; }

log() {
  printf '%s %s\n' "$(ts)" "$*" | tee -a "$LOG_FILE" >&2
}

die() {
  log "FATAL $*"
  exit 1
}

# Pick a python interpreter: prefer the project venv, fall back to PATH.
PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
[[ -n "$PY" ]] || die "no python interpreter found"

# ---- env ------------------------------------------------------------------

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.env"
  set +a
else
  die ".env is missing — copy .env.example to .env and fill it in"
fi

command -v claude >/dev/null 2>&1 || die "claude CLI is not on PATH"

mkdir -p "$RAW_DIR"

# ---- read dedup tunables from config.yaml --------------------------------

DEDUP_RECENT_DAYS="$("$PY" -c '
import yaml, sys
c = yaml.safe_load(open("config.yaml")) or {}
print(int(c.get("dedup", {}).get("recent_days", 14)))
')"
DEDUP_RECENT_BRIEFS="$("$PY" -c '
import yaml, sys
c = yaml.safe_load(open("config.yaml")) or {}
print(int(c.get("dedup", {}).get("recent_briefs_count", 14)))
')"

# ---- 1. fetchers ----------------------------------------------------------

log "STEP fetchers start"
ARXIV_OK=0
YT_OK=0
"$PY" -m jarvis.fetchers.arxiv > "$RAW_DIR/arxiv.json" 2>>"$LOG_FILE" && ARXIV_OK=1 \
  || log "WARN arxiv fetcher failed"
"$PY" -m jarvis.fetchers.youtube > "$RAW_DIR/youtube.json" 2>>"$LOG_FILE" && YT_OK=1 \
  || log "WARN youtube fetcher failed"
log "STEP fetchers done (arxiv=$ARXIV_OK youtube=$YT_OK)"

# Build the dedupe input list from whichever fetchers produced output.
DEDUPE_INPUTS=()
[[ -s "$RAW_DIR/arxiv.json" ]] && DEDUPE_INPUTS+=("$RAW_DIR/arxiv.json")
[[ -s "$RAW_DIR/youtube.json" ]] && DEDUPE_INPUTS+=("$RAW_DIR/youtube.json")

if [[ ${#DEDUPE_INPUTS[@]} -eq 0 ]]; then
  die "no fetcher output to feed into dedupe — aborting"
fi

# ---- 2. dedupe ------------------------------------------------------------

log "STEP dedupe start"
"$PY" -m jarvis.state dedupe "${DEDUPE_INPUTS[@]}" > "$RAW_DIR/new.json" 2>>"$LOG_FILE" \
  || die "dedupe failed"
NEW_COUNT="$("$PY" -c 'import json,sys; print(len(json.load(open("'"$RAW_DIR/new.json"'"))["items"]))')"
log "STEP dedupe done (new=$NEW_COUNT)"

# ---- 3. stage cross-day context for synthesis ----------------------------

log "STEP cross-day-context start"
"$PY" -m jarvis.state export-seen-recent \
  --days "$DEDUP_RECENT_DAYS" \
  --out "$RAW_DIR/seen_recent.txt" 2>>"$LOG_FILE" \
  || log "WARN export-seen-recent failed; deny-list will be empty"

# Stage the most recent N archived briefings for cross-day duplicate detection.
rm -rf "$RAW_DIR/recent_briefs"
mkdir -p "$RAW_DIR/recent_briefs"
if compgen -G "$ARCHIVE_DIR/*.md" > /dev/null; then
  # ls -t sorts newest first; head limits to N most recent.
  ls -t "$ARCHIVE_DIR"/*.md 2>/dev/null \
    | head -n "$DEDUP_RECENT_BRIEFS" \
    | xargs -I{} cp {} "$RAW_DIR/recent_briefs/" 2>>"$LOG_FILE"
fi
RECENT_BRIEFS_COUNT="$(ls "$RAW_DIR/recent_briefs"/*.md 2>/dev/null | wc -l | tr -d ' ')"
log "STEP cross-day-context done (deny-list, recent_briefs=$RECENT_BRIEFS_COUNT)"

# ---- 4. synthesis ---------------------------------------------------------

if [[ -f "$PROMPT_LOCAL" ]]; then
  PROMPT_PATH="$PROMPT_LOCAL"
  log "STEP synthesis using prompts/daily_brief.local.md"
else
  PROMPT_PATH="$PROMPT_FILE"
  log "STEP synthesis using prompts/daily_brief.md"
fi
[[ -f "$PROMPT_PATH" ]] || die "prompt file missing: $PROMPT_PATH"

# WebSearch and WebFetch are deny-by-default in `claude -p` headless mode;
# without these flags the prompt's heuristic search_themes branch silently
# no-ops (no career/leisure web coverage at all).
claude -p "$(cat "$PROMPT_PATH")" \
  --add-dir "$RAW_DIR" \
  --allowedTools "WebSearch" "WebFetch" \
  > "$BRIEFING_FILE" 2>>"$LOG_FILE" \
  || die "claude synthesis failed"

if [[ ! -s "$BRIEFING_FILE" ]]; then
  die "synthesis produced an empty briefing"
fi
log "STEP synthesis done ($(wc -c <"$BRIEFING_FILE" | tr -d ' ') bytes)"

# ---- 5. delivery ----------------------------------------------------------

log "STEP delivery start"
if "$PY" -m jarvis.deliver --quiet "$BRIEFING_FILE" 2>>"$LOG_FILE"; then
  log "STEP delivery done"
else
  die "delivery failed — skipping archive and mark-seen so items can be retried tomorrow"
fi

# ---- 6. archive the brief (only after successful delivery) ---------------
#
# Persist today's brief so the synthesis prompt can read recent days as
# cross-day duplicate-detection context on subsequent runs. Archive failure
# is non-fatal — mark-delivered still runs.

log "STEP archive-brief start"
mkdir -p "$ARCHIVE_DIR"
ARCHIVE_PATH="$ARCHIVE_DIR/$(date '+%Y-%m-%d').md"
if cp "$BRIEFING_FILE" "$ARCHIVE_PATH" 2>>"$LOG_FILE"; then
  log "STEP archive-brief done ($ARCHIVE_PATH)"
else
  log "WARN archive-brief failed; cross-day context for tomorrow will lack today's brief"
fi

# ---- 7. mark-seen (only after successful delivery) -----------------------
#
# Mark seen every URL that appears in the brief — fetcher items get their
# native category (arxiv, youtube), web_search-sourced URLs get category
# `web` so the deny-list catches them on subsequent runs.

log "STEP mark-seen start"
"$PY" -m jarvis.state mark-delivered \
  --new "$RAW_DIR/new.json" \
  --briefing "$BRIEFING_FILE" 2>>"$LOG_FILE" \
  || log "WARN mark-delivered failed; some items may be re-delivered tomorrow"
log "STEP mark-seen done"

log "RUN ok"
