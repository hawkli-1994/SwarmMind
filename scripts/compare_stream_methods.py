"""
对比测试：直接 stream vs stream_events
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.WARNING)
for name in ['httpcore', 'httpx', 'openai', 'anthropic']:
    logging.getLogger(name).setLevel(logging.WARNING)

from langchain_core.messages import HumanMessage

from swarmmind.agents.general_agent import DeerFlowRuntimeAdapter
from swarmmind.layered_memory import MemoryContext
from swarmmind.models import ConversationRuntimeOptions, ConversationMode
from swarmmind.runtime import ensure_default_runtime_instance


def test_direct_stream():
    """测试直接调用底层 stream"""
    print("\n" + "="*70)
    print("方法1: 直接调用 _client._agent.stream()")
    print("="*70)
    
    runtime_options = ConversationRuntimeOptions(
        mode=ConversationMode.ULTRA,
        thinking_enabled=True,
        plan_mode=True,
        subagent_enabled=True,
    )
    
    runtime_instance = ensure_default_runtime_instance()
    adapter = DeerFlowRuntimeAdapter(
        runtime_instance=runtime_instance,
        thinking_enabled=True,
        subagent_enabled=True,
        plan_mode=True,
    )
    
    thread_id = f"test-{uuid.uuid4().hex[:8]}"
    config = adapter._client._get_runnable_config(
        thread_id,
        thinking_enabled=True,
        plan_mode=True,
        subagent_enabled=True,
    )
    adapter._client._ensure_agent(config)
    
    user_msg_id = str(uuid.uuid4())
    goal = "写一句关于夏天的诗。"
    state = {"messages": [HumanMessage(content=goal, id=user_msg_id)]}
    context = {"thread_id": thread_id}
    
    events = []
    for mode_tag, chunk in adapter._client._agent.stream(
        state, config=config, context=context, stream_mode=["messages", "values"]
    ):
        events.append((mode_tag, type(chunk).__name__))
    
    print(f"事件数: {len(events)}")
    for i, (tag, chunk_type) in enumerate(events[:10]):
        print(f"  [{i}] {tag}: {chunk_type}")
    return len(events)


def test_stream_events():
    """测试通过 stream_events 调用"""
    print("\n" + "="*70)
    print("方法2: 通过 stream_events()")
    print("="*70)
    
    runtime_options = ConversationRuntimeOptions(
        mode=ConversationMode.ULTRA,
        thinking_enabled=True,
        plan_mode=True,
        subagent_enabled=True,
    )
    
    runtime_instance = ensure_default_runtime_instance()
    adapter = DeerFlowRuntimeAdapter(
        runtime_instance=runtime_instance,
        thinking_enabled=True,
        subagent_enabled=True,
        plan_mode=True,
    )
    
    ctx = MemoryContext(
        scope="test",
        session_id=f"test-{uuid.uuid4().hex[:8]}",
        user_id="test_user",
    )
    
    goal = "写一句关于夏天的诗。"
    
    events = []
    try:
        stream = adapter.stream_events(goal, ctx=ctx, runtime_options=runtime_options)
        while True:
            try:
                event = next(stream)
                events.append(event.get("type", "unknown"))
            except StopIteration:
                break
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"事件数: {len(events)}")
    for i, event_type in enumerate(events[:10]):
        print(f"  [{i}] {event_type}")
    return len(events)


def main():
    direct_count = test_direct_stream()
    events_count = test_stream_events()
    
    print("\n" + "="*70)
    print("对比结果")
    print("="*70)
    print(f"直接 stream:     {direct_count} 个事件")
    print(f"stream_events:   {events_count} 个事件")
    
    if events_count == 0 and direct_count > 0:
        print("\n⚠️ 问题确认: stream_events() 返回 0 事件，但直接调用正常！")
    elif events_count < direct_count:
        print(f"\n⚠️ 事件丢失: stream_events 丢失了 {direct_count - events_count} 个事件")
    else:
        print("\n✓ 两者结果一致")


if __name__ == "__main__":
    main()
