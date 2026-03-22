"""Unified LLM client — single place for all LLM API calls.

Phase 1: uses litellm for both streaming and non-streaming calls.
Phase 2: swap this implementation for any provider's SDK.
"""

import json
import logging
import os

import litellm

from swarmmind.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM errors."""
    pass


class LLMClient:
    """
    Unified LLM client.

    Uses httpx to call the configured provider's API directly.
    All agents and the renderer should use this class — never call
    the API directly in other modules.
    """

    def __init__(self):
        self.provider = LLM_PROVIDER
        self.model = LLM_MODEL
        self.api_key = LLM_API_KEY
        self.base_url = LLM_BASE_URL

        if not self.api_key:
            raise LLMError(
                f"No API key configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY. "
                f"provider={self.provider}"
            )

    def complete(self, prompt: str, max_tokens: int = 4096, reasoning: bool = False) -> str:
        """
        Send a prompt and return the LLM's text response.

        Args:
            prompt: the full prompt to send
            max_tokens: max tokens in response
            reasoning: whether to enable reasoning/thinking mode (default False for speed)

        Returns:
            The LLM's text response string.

        Raises:
            LLMError: on any failure (auth, timeout, parse error)
        """
        litellm_model = f"{self.provider}/{self.model}"
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": litellm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        # Disable thinking/reasoning mode for speed when not needed (DashScope qwen models)
        if not reasoning:
            kwargs["extra_body"] = {"think": False}

        # litellm respects this for per-request timeout
        kwargs["request_timeout"] = 120
        # Disable litellm's default retry behavior — DashScope qwen models
        # can be slow and retries compound latency. Fail fast instead.
        kwargs["max_retries"] = 0

        # Clear proxy env vars for this request to prevent proxy interference
        # DashScope calls should go direct, not through any proxy
        env_backup = {}
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            if var in os.environ:
                env_backup[var] = os.environ.pop(var)

        try:
            response = litellm.completion(**kwargs)
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("LLM completion error: %s", e)
            raise LLMError(f"LLM completion failed: {e}")
        finally:
            # Restore env vars
            os.environ.update(env_backup)

    async def stream(self, messages: list[dict], max_tokens: int = 1024, reasoning: bool = False):
        """
        Stream LLM response chunks as async generator.

        Yields:
            dict with optional 'content' or 'reasoning_content' text delta,
            and 'finish' when the stream ends.

        Args:
            messages: list of {"role": "user"|"assistant", "content": "..."}
            max_tokens: max tokens in response
            reasoning: whether to enable reasoning/thinking mode (default False for speed)
        """
        litellm_model = f"{self.provider}/{self.model}"
        kwargs = {
            "model": litellm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["api_base"] = self.base_url
        # Disable thinking/reasoning mode for speed when not needed (DashScope qwen models)
        if not reasoning:
            kwargs["extra_body"] = {"think": False}

        # Clear proxy env vars for this request to prevent proxy interference
        env_backup = {}
        for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            if var in os.environ:
                env_backup[var] = os.environ.pop(var)

        try:
            stream_resp = await litellm.acompletion(**kwargs)
            async for chunk in stream_resp:
                delta = chunk["choices"][0]["delta"]
                # "content" = actual response, "reasoning_content" = thinking chain
                content_text = delta.get("content") or ""
                reasoning_text = delta.get("reasoning_content") or ""
                finish = chunk["choices"][0]["finish_reason"]
                if reasoning_text:
                    yield {"thinking": reasoning_text, "finish": finish}
                if content_text:
                    yield {"text": content_text, "finish": finish}
        except Exception as e:
            logger.error("LLM stream error: %s", e)
            yield {"error": str(e), "finish": "stop"}
        finally:
            os.environ.update(env_backup)
