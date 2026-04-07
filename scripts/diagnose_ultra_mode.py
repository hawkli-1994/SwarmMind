"""
诊断脚本：验证不同模式下的事件流和模型输出

运行方式:
    cd /Users/krli/workspace/SwarmMindProject/SwarmMind
    uv run python scripts/diagnose_ultra_mode.py

测试场景:
1. THINKING 模式 - 基本推理能力
2. PRO 模式 - 规划模式
3. ULTRA 模式 - 子任务模式

输出: 每个模式的事件流日志，用于分析问题
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarmmind.agents.general_agent import DeerFlowRuntimeAdapter
from swarmmind.layered_memory import MemoryContext
from swarmmind.models import ConversationRuntimeOptions, ConversationMode

# 配置日志
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 禁用噪声日志
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)


class EventCollector:
    """收集和记录事件的诊断工具"""
    
    def __init__(self, mode: str):
        self.mode = mode
        self.events: list[dict] = []
        self.thinking_chunks: list[str] = []
        self.message_chunks: list[str] = []
        self.tool_calls: list[dict] = []
        self.tool_results: list[dict] = []
        
    def record_event(self, event: dict):
        """记录单个事件"""
        event_type = event.get("type", "unknown")
        
        if event_type == "assistant_reasoning":
            self.thinking_chunks.append(event.get("content", ""))
        elif event_type == "assistant_message":
            self.message_chunks.append(event.get("content", ""))
        elif event_type == "assistant_tool_calls":
            self.tool_calls.append(event)
        elif event_type == "tool_result":
            self.tool_results.append(event)
            
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            **event
        })
        
    def summarize(self) -> dict:
        """生成摘要报告"""
        return {
            "mode": self.mode,
            "total_events": len(self.events),
            "thinking_chunks": len(self.thinking_chunks),
            "message_chunks": len(self.message_chunks),
            "tool_calls": len(self.tool_calls),
            "tool_results": len(self.tool_results),
            "final_thinking": self.thinking_chunks[-1] if self.thinking_chunks else None,
            "final_message": self.message_chunks[-1] if self.message_chunks else None,
            "has_empty_final_message": not self.message_chunks or not self.message_chunks[-1].strip(),
        }


def test_mode(mode: ConversationMode, test_prompt: str) -> EventCollector:
    """测试指定模式的事件流"""
    
    print(f"\n{'='*60}")
    print(f"测试模式: {mode.value}")
    print(f"测试提示: {test_prompt}")
    print(f"{'='*60}\n")
    
    collector = EventCollector(mode.value)
    
    # 创建 adapter
    runtime_options = ConversationRuntimeOptions(
        mode=mode,
        model_name=None,  # 使用默认模型
        thinking_enabled=mode in (ConversationMode.THINKING, ConversationMode.PRO, ConversationMode.ULTRA),
        plan_mode=mode in (ConversationMode.PRO, ConversationMode.ULTRA),
        subagent_enabled=mode == ConversationMode.ULTRA,
    )
    
    # 创建临时 runtime instance
    from swarmmind.runtime import ensure_default_runtime_instance
    runtime_instance = ensure_default_runtime_instance()
    
    adapter = DeerFlowRuntimeAdapter(
        runtime_instance=runtime_instance,
        default_model=None,
        thinking_enabled=runtime_options.thinking_enabled,
        subagent_enabled=runtime_options.subagent_enabled,
        plan_mode=runtime_options.plan_mode,
    )
    
    # 创建 memory context (使用合法 thread_id 格式：仅 alphanumeric, hyphen, underscore)
    ctx = MemoryContext(
        scope="test",
        session_id=f"test-{mode.value}-{uuid.uuid4().hex[:8]}",
        user_id="test_user",
    )
    
    # 收集事件
    try:
        stream = adapter.stream_events(
            test_prompt,
            ctx=ctx,
            runtime_options=runtime_options,
        )
        
        final_text = ""
        tool_results = []
        
        while True:
            try:
                event = next(stream)
                collector.record_event(event)
                
                # 打印实时事件
                event_type = event.get("type", "unknown")
                if event_type == "assistant_reasoning":
                    print(f"[THINKING] {event.get('content', '')[:80]}...")
                elif event_type == "assistant_message":
                    print(f"[MESSAGE] {event.get('content', '')[:80]}...")
                elif event_type == "assistant_tool_calls":
                    tool_calls = event.get("tool_calls", [])
                    for tc in tool_calls:
                        print(f"[TOOL_CALL] {tc.get('name')}({tc.get('args', {})})")
                elif event_type == "tool_result":
                    print(f"[TOOL_RESULT] {event.get('tool_name')}: {event.get('content', '')[:60]}...")
                    
            except StopIteration as stop:
                final_text, tool_results = stop.value
                break
                
        print(f"\n[FINAL] final_text length: {len(final_text)}")
        print(f"[FINAL] final_text preview: {final_text[:200]}...")
        print(f"[FINAL] tool_results count: {len(tool_results)}")
        
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    return collector


def analyze_results(results: list[EventCollector]):
    """分析并对比不同模式的结果"""
    
    print(f"\n{'='*60}")
    print("诊断报告摘要")
    print(f"{'='*60}\n")
    
    for collector in results:
        summary = collector.summarize()
        print(f"\n模式: {summary['mode']}")
        print(f"  - 总事件数: {summary['total_events']}")
        print(f"  - Thinking 片段: {summary['thinking_chunks']}")
        print(f"  - Message 片段: {summary['message_chunks']}")
        print(f"  - Tool Calls: {summary['tool_calls']}")
        print(f"  - Tool Results: {summary['tool_results']}")
        print(f"  - 最终消息为空: {summary['has_empty_final_message']}")
        
        if summary['has_empty_final_message']:
            print(f"  ⚠️ 警告: {summary['mode']} 模式下最终消息为空!")
    
    # 保存详细日志到文件
    output_file = f"/tmp/swarmmind_diagnose_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    all_events = {
        collector.mode: {
            "summary": collector.summarize(),
            "events": collector.events
        }
        for collector in results
    }
    
    with open(output_file, 'w') as f:
        json.dump(all_events, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细日志已保存到: {output_file}")


def main():
    """主测试流程"""
    
    # 测试提示 - 简单但足够触发不同模式的行为
    test_prompts = {
        ConversationMode.THINKING: "写一个关于人工智能的短段落，3句话。",
        ConversationMode.PRO: "创建一个简单的待办事项列表应用的计划，包含3个步骤。",
        ConversationMode.ULTRA: "帮我分析一个简单的Python脚本的功能，并给出改进建议。脚本功能：读取CSV文件并统计行数。",
    }
    
    results = []
    
    for mode, prompt in test_prompts.items():
        try:
            collector = test_mode(mode, prompt)
            results.append(collector)
        except Exception as e:
            print(f"\n[CRITICAL ERROR] {mode.value} 模式测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 分析结果
    if results:
        analyze_results(results)
    
    print("\n诊断完成。")


if __name__ == "__main__":
    main()
