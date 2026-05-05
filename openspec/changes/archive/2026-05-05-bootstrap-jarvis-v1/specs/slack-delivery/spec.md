## ADDED Requirements

### Requirement: Slack incoming webhook delivery

The system SHALL provide a delivery module that posts the synthesized briefing markdown to a Slack incoming webhook URL. The URL MUST be sourced from the `SLACK_WEBHOOK_URL` environment variable, never embedded in code or committed configuration.

#### Scenario: Successful delivery

- **GIVEN** `SLACK_WEBHOOK_URL` is set to a valid Slack incoming webhook URL
- **WHEN** the delivery module is invoked with a markdown briefing
- **THEN** the module POSTs the briefing content to the webhook, receives an HTTP 2xx response, and exits zero

#### Scenario: Webhook URL not in committed code

- **WHEN** any reviewer searches the repository
- **THEN** no committed file contains a real Slack webhook URL; only `.env.example` mentions the variable name

### Requirement: Explicit failure on delivery error

When delivery fails (missing environment variable, network error, non-2xx HTTP response), the delivery module SHALL exit non-zero and write a diagnostic message to stderr identifying the failure mode.

#### Scenario: Missing webhook URL

- **WHEN** the delivery module runs without `SLACK_WEBHOOK_URL` set
- **THEN** the module exits non-zero and stderr names the missing variable

#### Scenario: Non-2xx response from Slack

- **WHEN** the webhook responds with HTTP 4xx or 5xx
- **THEN** the module exits non-zero and stderr includes the response status and body

#### Scenario: Failure prevents mark-seen

- **WHEN** delivery exits non-zero
- **THEN** the orchestrator does not invoke the seen-tracking mark-seen step for the items in this run

### Requirement: Briefing content is forwarded unchanged

The delivery module SHALL transmit the synthesized briefing exactly as produced by the synthesis step, without rewrapping, truncating, or otherwise mutating it.

#### Scenario: Briefing reaches Slack verbatim

- **WHEN** the delivery module receives a briefing of length L
- **THEN** the bytes posted to Slack render the same content the synthesis step produced, modulo only Slack's own rendering of markdown
