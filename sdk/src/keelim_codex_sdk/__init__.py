"""Small, explicit example of the official OpenAI Codex Python SDK."""

from __future__ import annotations

import argparse
from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run one prompt through the locally configured Codex runtime."""
    parser = argparse.ArgumentParser(
        description="Run one prompt with the locally configured Codex runtime."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Prompt to send. Required to start the Codex runtime.",
    )
    args = parser.parse_args(argv)
    if not args.prompt:
        parser.print_help()
        return 2

    # Import only after parsing so --help and missing-argument use stay offline.
    from openai_codex import ApprovalMode, Codex, Sandbox

    with Codex() as codex:
        thread = codex.thread_start(sandbox=Sandbox.read_only, approval_mode=ApprovalMode.deny_all)
        result = thread.run(args.prompt)
    print(result.final_response)
    return 0
