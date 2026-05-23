## Context

Five days of cron-driven runs produced clear quantitative evidence of two distinct dedup failures:

| run | delivered (fetcher) | dropped (fetcher) | observable web_search repeats |
|---|---|---|---|
| 5/6 | 7 | 200 | (first run) |
| 5/7 | 7 | 77 | Meta/ARI re-surfaced |
| 5/8 | 7 | 108 | Disney WDW wave re-surfaced |
| 5/9 | 5 | 99 | partial overlap |
| 5/10 | 2 | 0 | MM Falcon May 22 (different URL), Soarin' (different URL) |

The state DB at the time of design held 96 rows, all categorised `arxiv` (86) or `youtube` (10). Zero rows for `web_search`. The `mark_delivered` function only marks URLs whose item came through the dedupe envelope (`new.json`), and `web_search` results never go through that envelope — they are discovered by the synthesis prompt at synthesis time.

A human reading the briefs spots the repetitions easily: same event, different journalist, different URL. The current synthesis prompt is told to consolidate duplicates *within* a single brief (§3), but has no awareness of yesterday's brief. The model can, however, judge same-event identity across sources reliably when shown the prior brief — that is closer to how a human would handle it than any structured event-identity scheme we could design.

## Goals / Non-Goals

**Goals:**

- Stop the same `web_search`-source URL from re-appearing across days.
- Stop different sources covering the same already-delivered event from re-appearing across days, by giving the model the context to recognise it.
- Stabilise daily brief length so the user can predict roughly how much they will read each morning.
- Keep the existing `mark-delivered` failure semantics: a failed delivery does not advance the seen store, so items remain candidates for the next run.

**Non-Goals:**

- Structured event-identity hashes emitted by the model. Would catch same-event-different-source dedup deterministically, but requires an output-format contract the model has to honour every run, plus a schema migration. Defer to a follow-up if the prompt-context approach in this change proves insufficient.
- Long-horizon dedup beyond a small recent window. The maintainer's goal is reduced repetition, not perfect long-tail dedup.
- A web UI or query interface for the brief archive. The archive is a flat directory of dated markdown files; that is the interface.
- Compression of the brief archive. ~4 KB × 365 = ~1.5 MB/year. Bounded.

## Decisions

### 1. `mark-delivered` records every URL in the brief, not just the fetcher subset

**Decision:** Extract every URL from the brief text. For URLs whose hash already matches a row in `new_envelope`, behaviour is unchanged (they get `category = arxiv`/`youtube` from the matched item's id). For URLs that are *not* in the envelope, insert a row with `category = "web"` and the URL itself as the row's diagnostic context.

**Alternative considered:** Mark only the fetcher subset (status quo) and rely entirely on the recent-briefs context for cross-day dedup of `web_search`.

**Why rejected:** The recent-briefs context is heuristic — the model judges same-event identity. URL-level dedup is exact and free. Doing both gives a deterministic floor (URL never re-appears) plus a heuristic ceiling (different URLs covering the same event get caught when the model recognises them).

### 2. Surface the seen-recent set to the prompt as a flat URL list, not as a structured manifest

**Decision:** Export `/tmp/raw/seen_recent.txt`, one URL per line, sorted, recent-N-days only.

**Alternative considered:** JSON array, or a CSV with title/category/first_seen. Or feed only URL hashes (treating the model as a hash-comparator).

**Why rejected:**
- JSON adds parser overhead with no informational gain — the prompt only needs membership testing.
- Hashes only — the model cannot do hash equality; it would have to take the operator's word that a URL is "in" the deny-list. That defeats the point of the model being able to read the URLs to recognise patterns.
- Plain URLs let the model also notice obvious patterns (e.g., "I've seen `disneyparksblog.com/wdw/2026-disney-world-calendar-and-details/` on the deny-list, and the article I just found is `thepointsguy.com/news/...` on the same MM Falcon news; high probability of duplicate event").

### 3. Recent-briefs context is the last fourteen full briefings, copied into `/tmp/raw/recent_briefs/`

**Decision:** `run.sh` copies the fourteen most recent `state/briefings/*.md` into a per-run staging directory before invoking `claude -p`. The prompt reads them as part of `--add-dir`.

**Alternative considered:** Pass the previous *one* briefing only.

**Why rejected:** A leisure event ("성시경 콘서트 5/2·5/3·5/5") might be covered on 5/3 with one source and resurface on 5/8 with a fan-review article. A one-day window misses that.

**Alternative considered:** Match the heuristic-search window exactly (seven days, `window.heuristic_hours / 24`).

**Why rejected:** Same-event re-coverage by different outlets often lags the original event by more than a week — followup articles, retrospective angles, anniversary mentions. Fourteen days catches roughly two heuristic-window cycles of follow-up coverage at a marginal token cost (~50 KB) that remains within the headless `claude -p` budget.

**Alternative considered:** Pass thirty days.

**Why rejected:** Diminishing returns. The deny-list catches exact-URL repeats independently, so the brief-context channel only needs to cover the window in which the model can plausibly recognise same-event-different-source repetition. Fourteen days is comfortably above that threshold without inflating context cost.

### 4. Brief archive lives at `state/briefings/<YYYY-MM-DD>.md` and is gitignored

**Decision:** Mirror the existing `state/seen.sqlite` convention — generated state under `state/`, gitignored, never committed. Filenames are date-only (no weekday, no time-of-day) for sortability.

**Alternative considered:** Track the briefings in git so the maintainer's history is durably published.

**Why rejected:** Briefings contain `priority_keywords` excerpts, ticketing details, calendared events — non-secret but personal. The maintainer has accepted publishing config; daily personal news is a different threshold and benefits no one besides the maintainer.

### 5. Add a `dedup` block to `config.yaml` for two tunables

**Decision:** New `config.yaml` block:

```yaml
dedup:
  recent_days: 14            # how far back seen-URL deny-list reaches
  recent_briefs_count: 14    # how many past briefings the synthesis prompt reads
```

Both windows align at fourteen days. The deny-list and the brief context cover the same horizon, so cross-day dedup reasons over a single time scale.

**Alternative considered:** Hardcode both values.

**Why rejected:** Future tuning without code change. The defaults are sensible enough that a forker never needs to touch them.

### 6. Prompt distinguishes "drop" (URL match) from "drop or follow-up" (same-event match)

**Decision:** §3 (Consolidate duplicates) gains two clauses:

- *URL deny-list*: if a `web_search` result's URL appears in `seen_recent.txt`, drop it silently. No exceptions.
- *Same-event in recent_briefs*: if a `web_search` result covers the same underlying event already covered in `recent_briefs/*.md`, drop it unless there is genuinely new development (a date change, a price change, a status change). If there is new development, surface it as a follow-up entry, prefixed with `[update]` and citing the previous coverage.

**Why this asymmetry:** URL-level repetition is mechanical and never useful. Event-level repetition is sometimes useful — concert ticket dates can change, attractions can be delayed. The user wants the *new information*, not the n-th press rewrite. The `[update]` prefix lets the model surface real news while keeping noise out.

### 7. Plain-item cap at five per brief

**Decision:** §4 (Prioritize) gains a third cap: at most five plain (no-marker) items per brief. Combined with the existing 1 🔥 + 5 📌 caps, the brief ceiling is eleven items.

**Why:** The maintainer reports daily-length variability is part of the perceived noise. Cap → predictable shape. Five plain items per day, plus the priority items, is enough headroom for variety without sprawling.

## Risks / Trade-offs

- **[Risk] The model ignores `seen_recent.txt`.** LLM compliance with prompt-level rules is statistical. A failure mode would manifest as a known-seen URL still appearing in the brief. → **Mitigation:** the `seen_recent.txt` file is small and explicitly named in the prompt; non-compliance is observable in the brief and re-tunable in the prompt. The URL-record half of the change still benefits future runs even when the model occasionally slips.

- **[Risk] The model treats `recent_briefs/` content as additional source material rather than as context to filter against.** The model sees old briefings and accidentally re-cites items from them. → **Mitigation:** prompt §0 names `recent_briefs/` explicitly as "for cross-day duplicate-detection only — do not surface their items as fresh content"; the rule is stated in §3 too.

- **[Risk] The prompt's token budget grows with fourteen days of context.** Briefs are ~3–4 KB each, so fourteen days adds ~50 KB. Plus seen_recent (5–10 KB). Within `claude -p` headless budget, but if it ever pushes the budget, recent days drop first. → **Mitigation:** monitor synthesis-step duration in `run.log`; if it lengthens noticeably, tune `recent_briefs_count` down.

- **[Risk] First-run after deployment has empty `state/briefings/`, so the brief context is missing on day one.** → **Mitigation:** acceptable; the seen-URL deny-list still operates from existing 96 rows of `seen.sqlite`. The recent-briefs context fills in starting day two.

- **[Trade-off] Brief-archive directory accumulates personal data on disk.** Over a year, ~1–2 MB. Maintainer can prune by hand at any time without affecting state.

- **[Trade-off] The `[update]` follow-up convention is new and the model has to learn it from the prompt. Early runs may be inconsistent.** → **Mitigation:** observable in the brief; tighten the prompt wording in a follow-up if needed.

## Migration Plan

1. Land the change on a branch.
2. Code path `mark_delivered` widens — re-runs against any historical brief produce additional `web` rows alongside existing fetcher rows. No schema change.
3. `state/briefings/` directory is created on first successful run after merge. No backfill.
4. Cron picks up the next morning, runs against an empty `recent_briefs/` (first day) and a non-empty `seen_recent.txt` (existing 96 fetcher rows). Day-two run gets the day-one brief in context and the deny-list grows accordingly.
5. **Rollback:** revert the merge commit. Existing `seen.sqlite` rows with `category = "web"` become inert (the loader doesn't read category), no data loss. `state/briefings/` is left in place; harmless.
