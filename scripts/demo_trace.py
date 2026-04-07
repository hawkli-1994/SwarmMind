#!/usr/bin/env python3
"""
Demo script for collaboration trace feature.

This script demonstrates how the trace service reconstructs
collaboration trajectories from deer-flow checkpointer data.

Usage:
    uv run python scripts/demo_trace.py
"""

import json
import sqlite3
import tempfile
from pathlib import Path

from swarmmind.services.trace_service import TraceService


def create_sample_checkpointer_db(db_path: Path) -> str:
    """Create a sample checkpointer DB with realistic conversation flow."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint BLOB,
            metadata BLOB,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
    """)
    
    thread_id = "demo-conversation-001"
    base_time = "2026-04-07T10:00:00+00:00"
    
    # Simulate a realistic multi-agent collaboration
    checkpoints = [
        # 1. User asks for Q3 analysis
        {
            "id": "cp-001",
            "state": {
                "messages": [{"type": "human", "content": "帮我分析 Q3 财报，重点关注营收和利润趋势"}],
                "artifacts": [],
                "todos": []
            },
            "time": base_time
        },
        # 2. Lead agent plans and delegates
        {
            "id": "cp-002", 
            "state": {
                "messages": [
                    {"type": "human", "content": "帮我分析 Q3 财报，重点关注营收和利润趋势"},
                    {"type": "ai", "content": "我来帮您分析 Q3 财报。首先让我搜索相关数据。", "tool_calls": [
                        {"id": "tc-001", "name": "web_search", "args": {"query": "2025 Q3 财报 营收 利润"}}
                    ]}
                ],
                "artifacts": [],
                "todos": [
                    {"id": 1, "content": "搜索 Q3 财报数据", "done": False},
                    {"id": 2, "content": "分析营收趋势", "done": False},
                    {"id": 3, "content": "分析利润趋势", "done": False}
                ]
            },
            "time": "2026-04-07T10:00:05+00:00"
        },
        # 3. Tool execution result
        {
            "id": "cp-003",
            "state": {
                "messages": [
                    {"type": "human", "content": "帮我分析 Q3 财报，重点关注营收和利润趋势"},
                    {"type": "ai", "content": "我来帮您分析 Q3 财报。首先让我搜索相关数据。", "tool_calls": [
                        {"id": "tc-001", "name": "web_search", "args": {"query": "2025 Q3 财报 营收 利润"}}
                    ]},
                    {"type": "tool", "name": "web_search", "content": "Q3 财报数据：营收 100 亿，同比增长 15%；净利润 20 亿，同比增长 8%...", "tool_call_id": "tc-001"}
                ],
                "artifacts": [],
                "todos": [
                    {"id": 1, "content": "搜索 Q3 财报数据", "done": True},
                    {"id": 2, "content": "分析营收趋势", "done": False},
                    {"id": 3, "content": "分析利润趋势", "done": False}
                ]
            },
            "time": "2026-04-07T10:00:08+00:00"
        },
        # 4. Subagent delegation for deep analysis
        {
            "id": "cp-004",
            "state": {
                "messages": [
                    {"type": "human", "content": "帮我分析 Q3 财报，重点关注营收和利润趋势"},
                    {"type": "ai", "content": "我来帮您分析 Q3 财报。首先让我搜索相关数据。", "tool_calls": [
                        {"id": "tc-001", "name": "web_search", "args": {"query": "2025 Q3 财报 营收 利润"}}
                    ]},
                    {"type": "tool", "name": "web_search", "content": "Q3 财报数据：营收 100 亿，同比增长 15%；净利润 20 亿，同比增长 8%...", "tool_call_id": "tc-001"},
                    {"type": "ai", "content": "现在让我调用分析代理深入分析这些数据。", "tool_calls": [
                        {"id": "tc-002", "name": "task", "args": {
                            "description": "深度分析 Q3 营收",
                            "prompt": "分析 Q3 营收 100 亿同比增长 15% 的驱动因素...",
                            "subagent_type": "general-purpose"
                        }}
                    ]}
                ],
                "artifacts": [],
                "todos": [
                    {"id": 1, "content": "搜索 Q3 财报数据", "done": True},
                    {"id": 2, "content": "分析营收趋势", "done": True},
                    {"id": 3, "content": "分析利润趋势", "done": False}
                ]
            },
            "time": "2026-04-07T10:00:15+00:00"
        },
        # 5. Final response with artifact
        {
            "id": "cp-005",
            "state": {
                "messages": [
                    {"type": "human", "content": "帮我分析 Q3 财报，重点关注营收和利润趋势"},
                    {"type": "ai", "content": "我来帮您分析 Q3 财报。首先让我搜索相关数据。", "tool_calls": [
                        {"id": "tc-001", "name": "web_search", "args": {"query": "2025 Q3 财报 营收 利润"}}
                    ]},
                    {"type": "tool", "name": "web_search", "content": "Q3 财报数据：营收 100 亿，同比增长 15%；净利润 20 亿，同比增长 8%...", "tool_call_id": "tc-001"},
                    {"type": "ai", "content": "现在让我调用分析代理深入分析这些数据。", "tool_calls": [
                        {"id": "tc-002", "name": "task", "args": {
                            "description": "深度分析 Q3 营收",
                            "prompt": "分析 Q3 营收 100 亿同比增长 15% 的驱动因素...",
                            "subagent_type": "general-purpose"
                        }}
                    ]},
                    {"type": "ai", "content": "## Q3 财报分析总结\n\n**营收表现**：Q3 营收 100 亿元，同比增长 15%，主要驱动因素包括...\n\n**利润表现**：净利润 20 亿元，同比增长 8%，利润率保持稳定...\n\n详细分析报告已生成。"}
                ],
                "artifacts": ["/mnt/user-data/outputs/q3_analysis_report.md"],
                "todos": [
                    {"id": 1, "content": "搜索 Q3 财报数据", "done": True},
                    {"id": 2, "content": "分析营收趋势", "done": True},
                    {"id": 3, "content": "分析利润趋势", "done": True}
                ]
            },
            "time": "2026-04-07T10:01:30+00:00"
        }
    ]
    
    for i, cp in enumerate(checkpoints):
        parent_id = checkpoints[i-1]["id"] if i > 0 else None
        cursor.execute(
            """
            INSERT INTO checkpoints 
            (thread_id, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                cp["id"],
                parent_id,
                "checkpoint",
                json.dumps(cp["state"]),
                json.dumps({"created_at": cp["time"]})
            )
        )
    
    conn.commit()
    conn.close()
    return thread_id


def print_trace(trace: dict) -> None:
    """Pretty print a collaboration trace."""
    print("=" * 60)
    print(f"📝 会话轨迹: {trace['thread_id']}")
    print(f"📊 状态: {trace['status']}")
    print(f"💾 Checkpoints: {trace['checkpoint_count']}")
    print(f"📋 摘要: {trace['summary']}")
    print("=" * 60)
    
    print("\n📍 协作事件时间线:\n")
    
    for event in trace["events"]:
        event_type = event["type"]
        agent = event.get("agent_id", "unknown")
        status = event.get("agent_status", "")
        content = event.get("content", "")[:80]
        
        # Emoji icons for different event types
        icons = {
            "user_input": "👤",
            "assistant_response": "🤖",
            "subagent_dispatch": "🔀",
            "tool_execution": "🔧",
            "artifact_created": "📄",
            "todos_updated": "✅"
        }
        icon = icons.get(event_type, "•")
        
        print(f"  {icon} [{event_type}] {agent} ({status})")
        print(f"     └─ {content}...")
        
        # Extra details for specific event types
        if event_type == "subagent_dispatch" and "tool_calls" in event:
            for tc in event["tool_calls"]:
                print(f"        └─ 调用: {tc.get('name', 'unknown')}")
        elif event_type == "tool_execution":
            result = event.get("result", "")[:60]
            print(f"        └─ 结果: {result}...")
        elif event_type == "artifact_created":
            path = event.get("artifact_path", "")
            print(f"        └─ 路径: {path}")
        
        print()
    
    print("=" * 60)


def main():
    """Run the demo."""
    print("\n" + "=" * 60)
    print("  SwarmMind 协作轨迹演示")
    print("  (复用 deer-flow checkpointer 数据)")
    print("=" * 60 + "\n")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    try:
        # Create sample data
        print("🔄 创建示例 checkpointer 数据...")
        thread_id = create_sample_checkpointer_db(db_path)
        
        # Use TraceService to reconstruct
        print("🔍 使用 TraceService 重建协作轨迹...\n")
        service = TraceService(db_path)
        trace = service.get_conversation_trace(thread_id)
        
        # Print results
        print_trace(trace)
        
        # Print raw JSON (truncated)
        print("\n📦 完整轨迹数据 (JSON):")
        print("-" * 60)
        trace_json = json.dumps(trace, indent=2, ensure_ascii=False)
        # Print first 2000 chars
        print(trace_json[:2000])
        print("..." if len(trace_json) > 2000 else "")
        
        print("\n" + "=" * 60)
        print("✅ 演示完成！")
        print("=" * 60 + "\n")
        
    finally:
        # Cleanup
        db_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
