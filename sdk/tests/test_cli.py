from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from keelim_codex_sdk import main


class CliTests(unittest.TestCase):
    def test_help_does_not_import_or_start_sdk(self) -> None:
        with patch.dict("sys.modules", {"openai_codex": None}):
            with self.assertRaises(SystemExit) as raised:
                main(["--help"])
        self.assertEqual(raised.exception.code, 0)

    def test_missing_prompt_prints_help_without_starting_sdk(self) -> None:
        output = io.StringIO()
        with patch.dict("sys.modules", {"openai_codex": None}):
            with contextlib.redirect_stdout(output):
                result = main([])
        self.assertEqual(result, 2)
        self.assertIn("prompt", output.getvalue())

    def test_prompt_uses_read_only_sandbox_without_setting_model(self) -> None:
        class FakeApprovalMode:
            deny_all = "deny-all"

        class FakeSandbox:
            read_only = "read-only"

        class FakeTurn:
            final_response = "sample response"

        class FakeThread:
            def __init__(self) -> None:
                self.prompts: list[str] = []

            def run(self, prompt: str) -> FakeTurn:
                self.prompts.append(prompt)
                return FakeTurn()

        thread = FakeThread()
        codex_instances: list[FakeCodex] = []

        class FakeCodex:
            def __init__(self) -> None:
                codex_instances.append(self)

            def __enter__(self) -> FakeCodex:
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def thread_start(self, **kwargs: object) -> FakeThread:
                self.kwargs = kwargs
                return thread

        output = io.StringIO()
        with (
            patch("openai_codex.Codex", FakeCodex, create=True),
            patch("openai_codex.Sandbox", FakeSandbox, create=True),
            patch("openai_codex.ApprovalMode", FakeApprovalMode, create=True),
            contextlib.redirect_stdout(output),
        ):
            result = main(["Explain this code without changing files"])

        self.assertEqual(result, 0)
        self.assertEqual(thread.prompts, ["Explain this code without changing files"])
        self.assertEqual(
            codex_instances[0].kwargs,
            {
                "sandbox": FakeSandbox.read_only,
                "approval_mode": FakeApprovalMode.deny_all,
            },
        )
        self.assertEqual(output.getvalue().strip(), "sample response")


if __name__ == "__main__":
    unittest.main()
