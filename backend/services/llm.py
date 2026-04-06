"""LLM client abstraction — wraps Z.ai GLM 5.1 via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from backend.config import config

logger = logging.getLogger(__name__)


class LLMClient:
    """Thin wrapper around Z.ai's OpenAI-compatible GLM 5.1 API."""

    def __init__(self, api_key: str | None = None, model: str = "glm-5.1"):
        self._api_key = api_key or config.ZAI_API_KEY
        self._model_name = model
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url="https://api.z.ai/api/coding/paas/v4/",
        )

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> str:
        """Send a multi-turn chat and return the assistant reply as a string."""
        oai_messages = self._build_messages(messages, system_prompt)

        response = await self._client.chat.completions.create(
            model=self._model_name,
            messages=oai_messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def structured_output(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the LLM."""
        json_instruction = (
            "\n\nYou MUST respond with valid JSON only. No markdown fences, no "
            "commentary — just the raw JSON object."
        )
        full_system = (system_prompt or "") + json_instruction

        raw = await self.chat_completion(
            messages, system_prompt=full_system, temperature=temperature
        )

        # Strip markdown fences if the model adds them anyway
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return json.loads(cleaned)

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the model."""
        oai_messages = self._build_messages(messages, system_prompt)

        stream = await self._client.chat.completions.create(
            model=self._model_name,
            messages=oai_messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(
        messages: list[dict[str, str]], system_prompt: str = ""
    ) -> list[dict[str, str]]:
        """Convert [{role, content}] to OpenAI message format with system prompt."""
        oai_messages: list[dict[str, str]] = []

        if system_prompt:
            oai_messages.append({"role": "system", "content": system_prompt})

        for msg in messages:
            role = msg["role"]
            # Map custom roles to OpenAI standard roles
            if role in ("assistant", "friction", "model"):
                role = "assistant"
            elif role == "system":
                role = "system"
            else:
                role = "user"
            oai_messages.append({"role": role, "content": msg["content"]})

        return oai_messages
