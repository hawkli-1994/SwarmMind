"""LLM Status Renderer — generates human-readable status summaries on demand."""

import logging

import litellm

from swarmmind.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER
from swarmmind.shared_memory import SharedMemory

logger = logging.getLogger(__name__)


def render_status(goal: str) -> str:
    """
    LLM Status Renderer: given a goal, read all relevant shared context
    and generate a human-readable prose summary.

    Phase 1: returns prose summary only.
    Phase 2: LLM decides format (prose / table / Gantt).
    """
    # Read all shared memory for context
    memory = SharedMemory(agent_id="status_renderer")
    all_entries = memory.read_all()

    # Build context string for LLM
    if all_entries:
        context_lines = [
            f"[{entry['key']}] ({entry.get('domain_tags', 'unknown')}): {entry['value']}"
            for entry in all_entries
        ]
        context_block = "\n".join(context_lines)
    else:
        context_block = "(No shared context yet. The team has not accumulated any memory.)"

    prompt = f"""<system>
You are the SwarmMind Status Renderer. Your job is to synthesize a human-readable
status report from the team's accumulated context.

Given a goal and the current shared context, produce a clear, concise prose summary
that answers: "What is the current status of this project/goal?"

Keep it informative but not overly long. Highlight what's been done, what's in
progress, and what might be missing.
</system>

<goal>
{goal}
</goal>

<shared_context>
{context_block}
</shared_context>

Respond with ONLY a prose summary. No tables, no bullet lists, no code fences.
Just natural language that a human supervisor can quickly read to understand status."""

    try:
        # Configure litellm for DashScope Anthropic-compatible API
        if LLM_BASE_URL:
            litellm.api_base = LLM_BASE_URL

        # Use litellm for unified LLM API (supports 100+ providers including DashScope Anthropic)
        response = litellm.completion(
            model=f"{LLM_PROVIDER}/{LLM_MODEL}",
            messages=[{"role": "user", "content": prompt}],
            api_key=LLM_API_KEY,
            max_tokens=1024,
            temperature=0.4,
        )
        summary = response["choices"][0]["message"]["content"]
        return summary.strip()
    except Exception as e:
        logger.error("LLM Status Renderer error: %s", e)
        return (
            f"[Status renderer error: {e}] "
            f"Shared context has {len(all_entries)} entries. "
            f"Goal: {goal}"
        )
