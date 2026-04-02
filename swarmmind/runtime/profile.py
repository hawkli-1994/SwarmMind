"""Runtime profile resolution for the local DeerFlow runtime."""

from __future__ import annotations

import os

from swarmmind.config import LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER
from swarmmind.runtime.errors import RuntimeConfigError
from swarmmind.runtime.models import RuntimeProfile

DEFAULT_RUNTIME_PROFILE_ID = "local-default"


def resolve_default_runtime_profile() -> RuntimeProfile:
    """Resolve the single MVP runtime profile from environment-backed config."""
    provider = (os.environ.get("LLM_PROVIDER") or LLM_PROVIDER or "openai").strip().lower()
    model_name = (os.environ.get("LLM_MODEL") or LLM_MODEL or "").strip()
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    llm_base_url = os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("LLM_BASE_URL") or LLM_BASE_URL

    if not model_name:
        raise RuntimeConfigError("LLM_MODEL is required to build the default DeerFlow runtime profile.")

    if provider == "anthropic":
        if not anthropic_api_key:
            raise RuntimeConfigError("Missing ANTHROPIC_API_KEY for DeerFlow runtime.")
        model_class = "langchain_anthropic:ChatAnthropic"
        api_key_env_var = "ANTHROPIC_API_KEY"
    else:
        if not openai_api_key:
            raise RuntimeConfigError("Missing OPENAI_API_KEY for DeerFlow runtime.")
        model_class = "langchain_openai:ChatOpenAI"
        api_key_env_var = "OPENAI_API_KEY"

    return RuntimeProfile(
        runtime_profile_id=DEFAULT_RUNTIME_PROFILE_ID,
        provider=provider,
        model_name=model_name,
        model_class=model_class,
        api_key_env_var=api_key_env_var,
        base_url=llm_base_url or None,
        supports_vision=True,
    )
