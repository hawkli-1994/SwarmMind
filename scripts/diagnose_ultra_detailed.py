"""
详细诊断脚本：追踪 Ultra 模式的具体问题
"""

import json
import logging
import os
import sys
import traceback
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 禁用噪声日志
for name in ['httpcore', 'httpx', 'openai', 'anthropic']:
    logging.getLogger(name).setLevel(logging.WARNING)

from langchain_core.messages import AIMessageChunk, HumanMessage

from swarmmind.agents.general_agent import DeerFlowRuntimeAdapter
from swarmmind.layered_memory import MemoryContext
from swarmmind.models import ConversationRuntimeOptions, ConversationMode
from swarmmind.runtime import ensure_default_runtime_instance


def test_ultra_mode():
    """详细测试 Ultra 模式"""
    
    print("=" * 70)
    print("Ultra 模式详细诊断")
    print("=" * 70)
    
    # 创建 adapter
    runtime_options = ConversationRuntimeOptions(
        mode=ConversationMode.ULTRA,
        model_name=None,
        thinking_enabled=True,
        plan_mode=True,
        subagent_enabled=True,
    )
    
    runtime_instance = ensure_default_runtime_instance()
    
    print(f"\n[配置]")
    print(f"  thinking_enabled: {runtime_options.thinking_enabled}")
    print(f"  plan_mode: {runtime_options.plan_mode}")
    print(f"  subagent_enabled: {runtime_options.subagent_enabled}")
    
    adapter = DeerFlowRuntimeAdapter(
        runtime_instance=runtime_instance,
        default_model=None,
        thinking_enabled=runtime_options.thinking_enabled,
        subagent_enabled=runtime_options.subagent_enabled,
        plan_mode=runtime_options.plan_mode,
    )
    
    # 创建配置
    thread_id = f"test-ultra-{uuid.uuid4().hex[:8]}"
    config = adapter._client._get_runnable_config(
        thread_id,
        model_name=runtime_options.model_name,
        thinking_enabled=runtime_options.thinking_enabled,
        plan_mode=runtime_options.plan_mode,
        subagent_enabled=runtime_options.subagent_enabled,
    )
    
    print(f"\n[Thread ID] {thread_id}")
    print(f"[Config] {config}")
    
    # 确保 agent 创建
    adapter._client._ensure_agent(config)
    print(f"[Agent] 已创建")
    
    # 准备状态
    current_user_message_id = str(uuid.uuid4())
    goal = "写一个关于春天的短句。"
    state = {"messages": [HumanMessage(content=goal, id=current_user_message_id)]}
    runtime_context = {"thread_id": thread_id}
    
    print(f"\n[用户消息] {goal}")
    print(f"[消息ID] {current_user_message_id}")
    
    # 开始流式处理
    print(f"\n{'='*70}")
    print("开始流式处理...")
    print(f"{'='*70}\n")
    
    event_count = 0
    message_count = 0
    values_count = 0
    error_count = 0
    
    try:
        stream = adapter._client._agent.stream(
            state,
            config=config,
            context=runtime_context,
            stream_mode=["messages", "values"],
        )
        
        for mode_tag, chunk in stream:
            print(f"[{mode_tag.upper()}] ", end="")
            
            if mode_tag == "messages":
                message_count += 1
                msg_chunk, metadata = chunk
                
                if isinstance(msg_chunk, AIMessageChunk):
                    content = getattr(msg_chunk, "content", None)
                    reasoning = msg_chunk.additional_kwargs.get("reasoning_content", "")
                    chunk_id = getattr(msg_chunk, "id", None)
                    
                    print(f"AIMessageChunk id={chunk_id[:8] if chunk_id else None} "
                          f"content_len={len(content) if content else 0} "
                          f"reasoning_len={len(reasoning) if reasoning else 0}")
                    
                    if content:
                        print(f"  Content preview: {str(content)[:60]}...")
                    if reasoning:
                        print(f"  Reasoning preview: {str(reasoning)[:60]}...")
                else:
                    print(f"Non-AI chunk: {type(msg_chunk)}")
                    
            elif mode_tag == "values":
                values_count += 1
                messages = chunk.get("messages", [])
                print(f"State snapshot with {len(messages)} messages")
                
                for i, msg in enumerate(messages):
                    msg_type = type(msg).__name__
                    msg_id = getattr(msg, "id", None)
                    print(f"  [{i}] {msg_type} id={msg_id[:8] if msg_id else None}")
                    
            event_count += 1
            
            # 限制输出数量
            if event_count > 50:
                print("\n[达到事件上限，截断...]")
                break
                
    except Exception as e:
        error_count += 1
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("流式处理结束")
    print(f"{'='*70}")
    print(f"总事件数: {event_count}")
    print(f"Messages 事件: {message_count}")
    print(f"Values 事件: {values_count}")
    print(f"错误数: {error_count}")
    
    return error_count == 0 and event_count > 0


if __name__ == "__main__":
    success = test_ultra_mode()
    print(f"\n[结果] {'通过' if success else '失败'}")
    sys.exit(0 if success else 1)
