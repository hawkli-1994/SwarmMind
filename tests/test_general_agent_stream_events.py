"""Tests for DeerFlow event streaming in DeerFlowRuntimeAdapter."""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from swarmmind.agents.general_agent import DeerFlowRuntimeAdapter


class FakeStreamingAgent:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, state, config=None, context=None, stream_mode=None):
        assert state["messages"][0].id == "current-turn-user"
        for chunk in self._chunks:
            yield chunk


class FakeClient:
    def __init__(self, chunks):
        self._agent = FakeStreamingAgent(chunks)

    def _get_runnable_config(self, thread_id, model_name=None, thinking_enabled=True, plan_mode=False, subagent_enabled=False):
        return {
            "thread_id": thread_id,
            "model_name": model_name,
            "thinking_enabled": thinking_enabled,
            "plan_mode": plan_mode,
            "subagent_enabled": subagent_enabled,
        }

    def _ensure_agent(self, config):
        return None

    def _extract_text(self, content):
        return content if isinstance(content, str) else ""


def test_stream_events_skips_history_messages_before_current_turn(monkeypatch):
    monkeypatch.setattr("swarmmind.agents.general_agent.uuid.uuid4", lambda: "current-turn-user")

    agent = DeerFlowRuntimeAdapter.__new__(DeerFlowRuntimeAdapter)
    agent._client = FakeClient(
        [
            {
                "messages": [
                    HumanMessage(content="上一轮问题", id="history-user"),
                    AIMessage(content="上一轮回答", id="history-assistant"),
                    HumanMessage(content="这一轮问题", id="current-turn-user"),
                ],
            },
            {
                "messages": [
                    HumanMessage(content="上一轮问题", id="history-user"),
                    AIMessage(content="上一轮回答", id="history-assistant"),
                    HumanMessage(content="这一轮问题", id="current-turn-user"),
                    AIMessage(content="这一轮回答", id="current-turn-assistant"),
                ],
            },
        ],
    )
    agent._resolve_runtime_options = lambda runtime_options: SimpleNamespace(
        model_name="test-model",
        thinking_enabled=True,
        plan_mode=False,
        subagent_enabled=False,
    )
    agent._extract_reasoning = lambda message: ""

    events = list(
        agent.stream_events(
            "这一轮问题",
            ctx=SimpleNamespace(session_id="conversation-1"),
            runtime_options=SimpleNamespace(),
        ),
    )

    assert events == [
        {
            "type": "assistant_message",
            "message_id": "current-turn-assistant",
            "content": "这一轮回答",
        },
    ]
