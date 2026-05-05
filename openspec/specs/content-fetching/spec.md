## Purpose

How upstream sources (arXiv categories, YouTube channels) are queried and projected onto a single unified envelope schema consumed by downstream stages.

## Requirements

### Requirement: Unified fetcher output schema

Every fetcher SHALL emit a single JSON document on stdout conforming to the unified schema below. The top-level object MUST contain `source` (string identifying the fetcher), `fetched_at` (ISO 8601 timestamp with timezone), and `items` (array). Each item MUST contain `id` (stable identifier prefixed with the source name, e.g. `arxiv:2604.12345`), `title`, `url`, `published_at` (ISO 8601), `summary_raw`, and `metadata` (object with source-specific fields).

#### Scenario: arXiv fetcher emits valid schema

- **WHEN** the arXiv fetcher is invoked
- **THEN** its stdout is valid JSON with `source` equal to `"arxiv"`, a timezone-aware `fetched_at`, and an `items` array where every element has all required fields populated

#### Scenario: YouTube fetcher emits valid schema

- **WHEN** the YouTube fetcher is invoked
- **THEN** its stdout is valid JSON with `source` equal to `"youtube"`, a timezone-aware `fetched_at`, and an `items` array where every element has all required fields populated

### Requirement: arXiv cs.RO fetcher exhaustive coverage

The arXiv fetcher SHALL retrieve every paper newly published in the `cs.RO` category during the previous 24-hour window relative to invocation. Selection MUST NOT depend on popularity, citation count, or search relevance.

#### Scenario: All eligible papers appear

- **WHEN** the arXiv fetcher runs at time T
- **THEN** every `cs.RO` paper whose primary publication timestamp falls within the (T-24h, T) window appears in `items`, with no popularity-based filtering applied

#### Scenario: Window boundaries are documented

- **WHEN** any reviewer reads the arXiv fetcher's source or accompanying documentation
- **THEN** the precise definition of the 24-hour window (which timestamp is used, which timezone) is stated explicitly

### Requirement: YouTube channel enumeration fetcher

The YouTube fetcher SHALL enumerate the channels listed in the user's configuration and emit one item per video published by those channels within the previous 24-hour window. The fetcher MUST authenticate using a YouTube Data API v3 key sourced from the environment.

#### Scenario: New videos on a configured channel are emitted

- **WHEN** a configured channel publishes a new video within the lookback window and the YouTube fetcher runs
- **THEN** that video appears as an item with its title, canonical URL, publication timestamp, and channel identifier in `metadata`

#### Scenario: Missing API key fails fast

- **WHEN** the YouTube fetcher is invoked without `YOUTUBE_API_KEY` set in the environment
- **THEN** the fetcher exits non-zero with a stderr message naming the missing variable, and emits no JSON on stdout

### Requirement: Source list is configurable, not hard-coded

The set of arXiv categories and YouTube channels SHALL be defined in `config.local.yaml` (with safe defaults or examples in `config.yaml` and `config.local.yaml.example`). The fetchers MUST read this configuration at runtime; adding or removing a source MUST NOT require a code change.

#### Scenario: Forker swaps source list via config

- **WHEN** a forker edits `config.local.yaml` to change the arXiv categories or the YouTube channel ID list and re-runs the pipeline
- **THEN** the next fetcher invocation reflects the new list without any modification to files inside `jarvis/`

### Requirement: Transient failure does not abort the pipeline

When a fetcher cannot reach its upstream source (network failure, HTTP 5xx, malformed response), it SHALL emit a structurally valid JSON document with an empty `items` array and exit zero. The failure SHALL be recorded on stderr.

#### Scenario: arXiv RSS endpoint is unreachable

- **WHEN** the arXiv RSS endpoint times out or returns an HTTP 5xx response
- **THEN** the fetcher emits `{"source": "arxiv", "fetched_at": "...", "items": []}` on stdout, writes a diagnostic to stderr, and exits with status 0

#### Scenario: Pipeline continues without one fetcher's data

- **WHEN** one fetcher fails transiently but another succeeds
- **THEN** the orchestrator proceeds to dedupe and synthesis using whatever items were collected
