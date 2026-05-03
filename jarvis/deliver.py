"""Slack incoming-webhook delivery.

Reads `SLACK_WEBHOOK_URL` from the environment and POSTs a markdown briefing
as the message body. Exits non-zero on any failure (missing variable, network
error, non-2xx response). On success, exits zero.

Briefing source:
- A path argument, OR
- stdin if no argument is given or the argument is "-".
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

ENV_VAR = "SLACK_WEBHOOK_URL"
HTTP_TIMEOUT = 30.0


def _read_briefing(path: str | None) -> str:
    if path is None or path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def dispatch(briefing: str, webhook_url: str) -> None:
    """Post the briefing to a Slack incoming webhook.

    Raises httpx.HTTPError or RuntimeError on failure.
    """
    response = httpx.post(
        webhook_url,
        json={"text": briefing},
        timeout=HTTP_TIMEOUT,
    )
    if response.status_code // 100 != 2:
        raise RuntimeError(
            f"Slack returned HTTP {response.status_code}: {response.text!r}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Post a markdown briefing to Slack via incoming webhook."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to the briefing file. Use '-' or omit to read stdin.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the success line on stdout.",
    )
    args = parser.parse_args(argv)

    webhook_url = os.environ.get(ENV_VAR, "").strip()
    if not webhook_url:
        print(f"[deliver] {ENV_VAR} is not set", file=sys.stderr)
        return 2

    briefing = _read_briefing(args.path)
    if not briefing.strip():
        print("[deliver] briefing is empty; refusing to post", file=sys.stderr)
        return 3

    try:
        dispatch(briefing, webhook_url)
    except httpx.HTTPError as exc:
        print(f"[deliver] network error: {exc}", file=sys.stderr)
        return 4
    except RuntimeError as exc:
        print(f"[deliver] {exc}", file=sys.stderr)
        return 5

    if not args.quiet:
        print("[deliver] briefing posted to Slack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
