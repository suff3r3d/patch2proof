"""The OpenAI-compatible DeepSeek endpoint needs tool-based structured output."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from patch2proof.llm import _invoke_structured
from patch2proof.models import ReasoningMode


class _Result(BaseModel):
    answer: str


class _FakeModel:
    calls: list[dict] = []
    prompts: list[str] = []

    def __init__(self, **kwargs):
        self.options = kwargs

    def with_structured_output(self, schema, **kwargs):
        self.calls.append(kwargs)
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return {"answer": "ok"}


class DeepSeekCompatibilityTests(unittest.TestCase):
    def setUp(self):
        _FakeModel.calls = []
        _FakeModel.prompts = []

    def _invoke(self, env):
        with patch.dict(os.environ, env, clear=True):
            with patch(
                "patch2proof.llm.importlib.import_module",
                return_value=SimpleNamespace(ChatOpenAI=_FakeModel),
            ):
                result, provider = _invoke_structured(
                    ReasoningMode.OPENAI,
                    _Result,
                    system="Return a result",
                    human="Input",
                    model_name="deepseek-flash",
                    temperature=0,
                )
        self.assertEqual(result.answer, "ok")
        self.assertEqual(provider, "openai")

    def test_deepseek_base_url_uses_json_mode(self):
        self._invoke({"OPENAI_BASE_URL": "https://api.deepseek.com"})
        self.assertEqual(_FakeModel.calls, [{"method": "json_mode"}])
        self.assertIn('"answer"', _FakeModel.prompts[0])

    def test_openai_base_url_keeps_default(self):
        self._invoke({"OPENAI_BASE_URL": "https://api.openai.com/v1"})
        self.assertEqual(_FakeModel.calls, [{}])

    def test_explicit_api_base_takes_precedence(self):
        self._invoke({
            "OPENAI_API_BASE": "https://api.openai.com/v1",
            "OPENAI_BASE_URL": "https://api.deepseek.com",
        })
        self.assertEqual(_FakeModel.calls, [{}])


if __name__ == "__main__":
    unittest.main()
