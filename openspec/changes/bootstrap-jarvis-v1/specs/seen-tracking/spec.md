## ADDED Requirements

### Requirement: Persistent seen-item store

The system SHALL persist delivered-item identifiers in a SQLite database at `state/seen.sqlite`. The schema MUST include a primary-key column for the URL hash, a timestamp for first-seen time, and a category label.

#### Scenario: Database is created on first run

- **WHEN** the pipeline runs for the first time and `state/seen.sqlite` does not yet exist
- **THEN** the dedupe step creates the database with the required schema and proceeds without error

#### Scenario: Database file is gitignored

- **WHEN** any user inspects the repository's `.gitignore`
- **THEN** `state/seen.sqlite` is listed as ignored, and `git status` does not show it after a pipeline run

### Requirement: Dedupe filter on fetcher output

The system SHALL provide a dedupe operation that consumes the combined fetcher output and writes a filtered subset containing only items whose URL hash is not present in the seen store. The output MUST preserve the unified fetcher schema.

#### Scenario: Previously delivered item is filtered out

- **GIVEN** the seen store already contains the URL hash for item X
- **WHEN** dedupe runs over fetcher output that includes item X
- **THEN** the output JSON does not contain item X, and the structural schema is preserved

#### Scenario: All items are new

- **GIVEN** the seen store is empty
- **WHEN** dedupe runs over fetcher output containing N items
- **THEN** the output JSON contains all N items in the same schema

### Requirement: Mark-seen runs only after successful delivery

The system SHALL record new URL hashes in the seen store only after the Slack delivery step has completed successfully. If delivery fails or is skipped, the seen store MUST remain unchanged so the next run can retry the same items.

#### Scenario: Delivery succeeds

- **WHEN** Slack delivery returns success and the orchestrator invokes mark-seen with the delivered items
- **THEN** every URL hash in the delivered set is inserted into the seen store with the current timestamp and its category

#### Scenario: Delivery fails

- **WHEN** Slack delivery returns a non-success exit code
- **THEN** the orchestrator does not invoke mark-seen, and the seen store contains no records for items in the failed run

#### Scenario: Retry on next run delivers the same items

- **GIVEN** a previous run failed before mark-seen executed
- **WHEN** the next run executes
- **THEN** dedupe still considers the previously-undelivered items as new and they are re-included in synthesis input

### Requirement: URL-hash key stability

The system SHALL compute the dedupe key as a deterministic hash over the canonical URL (after any normalization the system performs). The same URL MUST always produce the same key across runs and machines.

#### Scenario: Same URL across runs hashes identically

- **WHEN** the same canonical URL is hashed in two separate runs (or on two different machines using the same code)
- **THEN** both invocations produce byte-identical hash values
