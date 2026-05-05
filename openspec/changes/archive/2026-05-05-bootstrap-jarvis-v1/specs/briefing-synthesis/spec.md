## ADDED Requirements

### Requirement: Headless Claude Code invocation

The synthesis step SHALL invoke Claude Code in headless mode using the `claude -p` (`--print`) flag, passing the contents of `prompts/daily_brief.md` as the prompt body and `--add-dir` to expose the directory containing the deduped fetcher JSON. The invocation MUST capture stdout as the synthesized briefing.

#### Scenario: Standard invocation produces a briefing on stdout

- **WHEN** the orchestrator runs `claude -p "$(cat prompts/daily_brief.md)" --add-dir <raw-dir>`
- **THEN** the command exits zero and writes a markdown briefing to stdout, which the orchestrator redirects to the briefing artifact path

#### Scenario: Invocation does not require an interactive session

- **WHEN** the synthesis step runs from cron with no controlling TTY
- **THEN** the invocation completes without prompting and produces the same artifact it would in an interactive shell

### Requirement: User profile is injected into synthesis

The prompt contract SHALL cause Claude Code to read the user's `profile.local.yaml` (job role, priority keywords, upcoming events) at the start of synthesis and use it to bias categorization and prioritization. The committed prompt MUST never embed any individual user's personal context.

#### Scenario: Synthesis reflects the configured profile

- **GIVEN** `profile.local.yaml` declares specific priority keywords and upcoming events
- **WHEN** synthesis runs
- **THEN** items related to the declared keywords or events are prioritized in the briefing

#### Scenario: Committed prompt is generic

- **WHEN** any reviewer inspects `prompts/daily_brief.md`
- **THEN** the file contains no real names, employers, project codenames, or trip dates of any individual user

### Requirement: Deterministic and heuristic instructions are clearly separated

The prompt SHALL contain two clearly distinguishable instruction blocks: one directing Claude Code to read and categorize the deterministic JSON inputs in the exposed directory, and another directing Claude Code to perform `web_search` queries for keyword-shaped sources. Each block MUST list the categories or keyword themes it covers.

#### Scenario: Reviewer can identify the two paths

- **WHEN** any reviewer reads `prompts/daily_brief.md`
- **THEN** the deterministic-JSON instructions and the `web_search` instructions are in separate, labeled sections

### Requirement: 24-hour publication time filter

The prompt SHALL inject the current date and instruct synthesis to include only items published within the previous 24 hours, and to exclude any item whose publication time cannot be determined.

#### Scenario: Old item is excluded

- **GIVEN** synthesis input includes an item published 48 hours before the run
- **WHEN** synthesis runs
- **THEN** the briefing does not contain that item

#### Scenario: Item without timestamp is excluded

- **GIVEN** a `web_search` result lacks a parseable publication timestamp
- **WHEN** synthesis runs
- **THEN** that result is omitted from the briefing

### Requirement: Priority-marker caps

The prompt SHALL cap high-priority markers to prevent inflation: at most one 🔥 (top item) per day, and at most five 📌 (notable items) per day, across the entire briefing.

#### Scenario: Cap is enforced

- **WHEN** synthesis identifies more than one candidate top item
- **THEN** the briefing contains at most one 🔥 marker

#### Scenario: Notable cap is enforced

- **WHEN** synthesis identifies more than five candidate notable items
- **THEN** the briefing contains at most five 📌 markers, and the rest are demoted or omitted

### Requirement: Duplicate-event consolidation

The prompt SHALL instruct synthesis to merge multiple sources reporting the same underlying event into a single briefing entry, citing the most primary or original source.

#### Scenario: Same event covered by multiple outlets

- **GIVEN** three news items in the input cover the same product launch
- **WHEN** synthesis runs
- **THEN** the briefing contains one consolidated entry for that launch, with the most primary source URL

### Requirement: Output format is JARVIS-voice Slack-compatible markdown

The prompt SHALL fix the output format: a JARVIS-voice opener and closer (e.g. "Good morning, sir." / "That will be all, sir."), Slack-compatible markdown for the body, and a source URL on every item. The character voice MUST appear in the user-visible body only and MUST NOT appear in configuration keys, error messages, or internal artifacts.

#### Scenario: Briefing has the expected envelope

- **WHEN** any briefing is generated
- **THEN** it begins with a JARVIS-voice opener line, ends with a JARVIS-voice closer line, and uses Slack-rendered markdown structure between them

#### Scenario: Every item has a source URL

- **WHEN** any briefing is generated
- **THEN** every individual item entry contains a clickable source URL

### Requirement: Optional local prompt override

The system SHALL permit a forker to maintain a `prompts/daily_brief.local.md` variant containing personal augmentations. When present, the orchestrator SHALL prefer the local variant over the committed `prompts/daily_brief.md`. The local variant MUST be gitignored.

#### Scenario: Local variant takes precedence

- **GIVEN** both `prompts/daily_brief.md` and `prompts/daily_brief.local.md` exist
- **WHEN** the orchestrator selects the prompt to invoke
- **THEN** it passes the contents of `prompts/daily_brief.local.md` to `claude -p`

#### Scenario: Local variant is not committed

- **WHEN** any reviewer inspects `.gitignore`
- **THEN** `prompts/daily_brief.local.md` (or a glob covering it) is listed
