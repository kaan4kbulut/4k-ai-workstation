"""CLI süreç hataları ve görevler arası yalıtım için çevrimdışı testler."""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from core.dispatcher import Dispatcher
from wrappers.claude_code_wrapper import ClaudeCodeWrapper
from wrappers.codex_wrapper import CodexWrapper
from wrappers.hermes_wrapper import HermesWrapper
from wrappers.opencode_wrapper import OpenCodeWrapper


class StubWrapper:
    name = "Stub"

    def __init__(self, response="tamam"):
        self.response = response

    async def execute(self, prompt):
        return self.response


class DispatchReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_nonzero_exit_never_returns_partial_output_or_secrets(self):
        for wrapper_class in (
            CodexWrapper, ClaudeCodeWrapper, HermesWrapper, OpenCodeWrapper,
        ):
            for stdout in (b"Partial answer containing secret-value", b""):
                with self.subTest(wrapper=wrapper_class.__name__, stdout=bool(stdout)):
                    process = AsyncMock()
                    process.returncode = 1
                    process.communicate.return_value = (stdout, b"token=secret-value")
                    with patch("asyncio.create_subprocess_exec", return_value=process):
                        result = await wrapper_class(binary="fake-cli").execute("test")
                    self.assertTrue(result.startswith("Hata:"), result)
                    self.assertIn("exit 1", result)
                    self.assertNotIn("secret-value", result)

    async def test_cli_success_preserves_answer(self):
        for wrapper_class in (
            CodexWrapper, ClaudeCodeWrapper, HermesWrapper, OpenCodeWrapper,
        ):
            with self.subTest(wrapper=wrapper_class.__name__):
                process = AsyncMock()
                process.returncode = 0
                process.communicate.return_value = (b"answer", b"")
                with patch("asyncio.create_subprocess_exec", return_value=process):
                    result = await wrapper_class(binary="fake-cli").execute("test")
                self.assertEqual(result, "answer")

    async def test_workspace_is_isolated_between_concurrent_and_later_calls(self):
        class WorkspaceWrapper(StubWrapper):
            async def execute(self, prompt):
                await asyncio.sleep(0)
                return str(getattr(self, "workspace", None))

        dispatcher = Dispatcher()
        wrapper = WorkspaceWrapper()
        dispatcher.register_wrapper("Stub", wrapper)
        with tempfile.TemporaryDirectory() as root:
            first = os.path.join(root, "first")
            second = os.path.join(root, "second")
            os.mkdir(first)
            os.mkdir(second)
            results = await asyncio.gather(
                dispatcher.dispatch("Stub", "a", workspace=first),
                dispatcher.dispatch("Stub", "b", workspace=second),
            )
            self.assertEqual(results, [first, second])
            self.assertEqual(await dispatcher.dispatch("Stub", "c"), "None")
            self.assertFalse(hasattr(wrapper, "workspace"))
            bad = await dispatcher.dispatch("Stub", "d", workspace=os.path.join(root, "missing"))
            self.assertTrue(bad.startswith("Hata:"))

    async def test_unknown_candidates_do_not_invoke_unrequested_wrapper(self):
        dispatcher = Dispatcher()
        wrapper = StubWrapper()
        wrapper.execute = AsyncMock(return_value="unrequested")
        dispatcher.register_wrapper("Stub", wrapper)
        for candidates in (["unknown"], []):
            result = await dispatcher.dispatch_with_escalation(candidates, "test")
            self.assertTrue(result["response"].startswith("Hata:"))
            self.assertEqual(result["attempts"], [])
        wrapper.execute.assert_not_awaited()

    async def test_invalid_responses_and_cost_block_escalate(self):
        for invalid in (None, 7, {}, "", "   ", "🔒 SIFIR HARCAMA KİLİDİ: Engellendi."):
            with self.subTest(response=invalid):
                dispatcher = Dispatcher()
                dispatcher.register_wrapper("first", StubWrapper(invalid))
                dispatcher.register_wrapper("fallback", StubWrapper("yanıt"))
                result = await dispatcher.dispatch_with_escalation(["first", "fallback"], "test")
                self.assertEqual(result["model"], "fallback")
                self.assertEqual(result["response"], "yanıt")
                self.assertEqual([attempt["success"] for attempt in result["attempts"]], [False, True])


if __name__ == "__main__":
    unittest.main()
