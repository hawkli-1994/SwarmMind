# DeerAgent 设计方案

> 状态：草稿
> 基于 DeerFlow v2.0 (`bytedance/deer-flow`)

## 一、目标

将 DeerFlow 封装为 SwarmMind 的一个 specialized agent（`DeerAgent`），用于处理**长程复杂任务**。

- SwarmMind 保持为**编排层**（routing、approval、context management）
- DeerFlow 作为**执行引擎**（tool execution、subagent orchestration、memory、checkpointing）
- 各司其职，不破坏现有架构

---

## 二、为什么需要 DeerAgent

SwarmMind 当前 agent（FinanceAgent、CodeReviewAgent）特点：
- 接收目标 → LLM 推理 → 生成 proposal → 人类审批 → 执行
- 适合**短程、结构化**任务

DeerFlow 擅长：
- 多步复杂推理（subagent decomposition）
- 工具执行（bash、web search、file I/O）
- 长程任务（checkpointing 持久化）
- Skills 系统（可插拔 prompt 片段）

**互补而非竞争。** DeerAgent 是 SwarmMind agent 能力的**增强**，而非替代。

---

## 三、架构设计

```
Human Supervisor
       │
       ▼
┌──────────────────┐     ┌─────────────────────────────────────────┐
│   Supervisor UI  │     │          Context Broker                  │
│   (shadcn/ui)    │ ←── │  routes goals → agents                   │
└──────────────────┘     └──────────┬──────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────────────┐
│   Finance   │          │   Code       │          │      DeerAgent       │
│   Agent     │          │   Review     │          │  (wraps DeerFlow)    │
│              │          │   Agent     │          │                      │
└──────────────┘          └──────────────┘          │  ┌────────────────┐  │
                                                      │  │ DeerFlowClient│  │
                                                      │  │ (embedded)    │  │
                                                      │  └───────┬───────┘  │
                                                      │          │          │
                                                      │  ┌───────▼───────┐  │
                                                      │  │ LangGraph     │  │
                                                      │  │ Agent Runtime │  │
                                                      │  │ + Tools       │  │
                                                      │  │ + Subagents   │  │
                                                      │  │ + Memory      │  │
                                                      │  │ + Skills      │  │
                                                      │  └───────────────┘  │
                                                      └──────────────────────┘
                                    │                           │
                                    └───────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │   Shared Memory   │
                                    │  (LayeredMemory)  │
                                    └───────────────────┘
```

### 关键设计原则

1. **DeerAgent 是 SwarmMind 的 agent**，遵循相同接口（接收 goal → 生成 proposal → 执行）
2. **DeerFlow 是执行引擎**，DeerFlowClient 以 embeded 模式运行（无 server 进程）
3. **SwarmMind 保持控制**，DeerAgent 执行结果写入 shared memory，人类可通过 UI 监控
4. **隔离性好**，DeerFlow 的 LangGraph 依赖不会扩散到整个 SwarmMind

---

## 四、接口设计

### 4.1 DeerAgent 类

```python
# swarmmind/agents/deer_agent.py

import asyncio
import logging
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator

from deerflow.client import DeerFlowClient, StreamEvent

from swarmmind.shared_memory import SharedMemory

logger = logging.getLogger(__name__)


class DeerAgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """DeerAgent 执行结果"""

    status: DeerAgentStatus
    final_text: str = ""
    artifacts: list[str] = None  # 产出的文件路径
    error: str | None = None


class DeerAgent:
    """Wraps DeerFlow as a SwarmMind agent.

    Receives complex/long-running goals from ContextBroker,
    executes via embedded DeerFlowClient, writes results to shared memory.
    """

    # 关键词路由：DeerAgent 接收这些关键词的目标
    ROUTING_KEYWORDS = [
        "research", "deep research", "analyze", "investigate",
        "compare", "evaluate", "study", "explore",
        "build", "create", "implement",  # 复杂构建任务
        "benchmark", "survey",
    ]

    def __init__(
        self,
        shared_memory: SharedMemory,
        deer_flow_config_path: str | None = None,
        default_model: str | None = None,
        thinking_enabled: bool = True,
        subagent_enabled: bool = True,
    ):
        """Initialize DeerAgent.

        Args:
            shared_memory: SwarmMind shared memory instance
            deer_flow_config_path: Path to DeerFlow's config.yaml
            default_model: Override default model from DeerFlow config
            thinking_enabled: Enable extended thinking mode
            subagent_enabled: Enable subagent decomposition
        """
        self.shared_memory = shared_memory
        self._client = DeerFlowClient(
            config_path=deer_flow_config_path,
            model_name=default_model,
            thinking_enabled=thinking_enabled,
            subagent_enabled=subagent_enabled,
        )
        self._status = DeerAgentStatus.IDLE

    @classmethod
    def can_handle(cls, goal: str) -> bool:
        """Check if this agent can handle the given goal."""
        goal_lower = goal.lower()
        return any(kw in goal_lower for kw in cls.ROUTING_KEYWORDS)

    async def execute(self, goal: str, thread_id: str | None = None) -> ExecutionResult:
        """Execute a goal via DeerFlow.

        Args:
            goal: The task goal from ContextBroker
            thread_id: Optional thread ID for multi-turn context

        Returns:
            ExecutionResult with final text and artifacts
        """
        if thread_id is None:
            thread_id = f"deer-{uuid.uuid4().hex[:8]}"

        self._status = DeerAgentStatus.RUNNING
        logger.info(f"DeerAgent starting: goal={goal[:50]}..., thread_id={thread_id}")

        try:
            final_text = ""
            artifacts = []

            # Stream results from DeerFlow
            async for event in self._stream_events(goal, thread_id):
                if event["type"] == "messages-tuple":
                    msg = event["data"]
                    if msg.get("msg_type") == "ai" and msg.get("content"):
                        final_text = msg["content"]
                    elif msg.get("msg_type") == "tool":
                        logger.debug(f"Tool call: {msg.get('name')}")

                elif event["type"] == "values":
                    # State snapshot — check for artifacts
                    if event["data"].get("artifacts"):
                        artifacts.extend(event["data"]["artifacts"])

            # Write result to SwarmMind shared memory
            await self._write_result(goal, final_text, artifacts, thread_id)

            self._status = DeerAgentStatus.COMPLETED
            return ExecutionResult(
                status=DeerAgentStatus.COMPLETED,
                final_text=final_text,
                artifacts=artifacts,
            )

        except Exception as e:
            logger.exception(f"DeerAgent failed: {e}")
            self._status = DeerAgentStatus.FAILED
            return ExecutionResult(
                status=DeerAgentStatus.FAILED,
                error=str(e),
            )

    async def _stream_events(self, goal: str, thread_id: str) -> AsyncGenerator[dict, None]:
        """Stream DeerFlow events as async generator.

        DeerFlowClient.stream() is a sync generator, so we run it in a thread pool.
        """
        loop = asyncio.get_event_loop()

        def sync_stream():
            return self._client.stream(goal, thread_id=thread_id)

        for event in await loop.run_in_executor(None, sync_stream):
            yield {
                "type": event.type,
                "data": event.data,
            }

    async def _write_result(
        self,
        goal: str,
        final_text: str,
        artifacts: list[str],
        thread_id: str,
    ) -> None:
        """Write execution result to SwarmMind shared memory."""
        memory_key = f"deer_agent:{thread_id}:result"
        result_data = {
            "goal": goal,
            "final_text": final_text,
            "artifacts": artifacts,
            "thread_id": thread_id,
        }
        await self.shared_memory.set(memory_key, result_data)

    def get_status(self) -> DeerAgentStatus:
        """Get current agent status."""
        return self._status

    def reset(self) -> None:
        """Reset agent state."""
        self._client.reset_agent()
        self._status = DeerAgentStatus.IDLE
```

### 4.2 与 ContextBroker 的集成

```python
# swarmmind/context_broker.py 改动

from swarmmind.agents.deer_agent import DeerAgent

class ContextBroker:
    def __init__(self, ...):
        self.deer_agent = DeerAgent(
            shared_memory=self.shared_memory,
            deer_flow_config_path=settings.DEER_FLOW_CONFIG_PATH,
        )

    def dispatch(self, goal: str) -> DispatchResult:
        # 路由逻辑
        if DeerAgent.can_handle(goal):
            # 返回一个特殊的 dispatch result，告知调用方用 DeerAgent 执行
            return DispatchResult(
                routed_to="deer_agent",
                agent=self.deer_agent,
                goal=goal,
            )
        # ... 其他路由逻辑
```

### 4.3 Supervisor API 扩展

```
POST /dispatch  (已有)
  └── body: { goal: string, agent?: string }
      ├── agent = "deer" or absent → DeerAgent
      └── returns { thread_id, status: "running" }

GET  /deer/{thread_id}/status
  └── returns { status, progress?, final_text?, artifacts? }

GET  /deer/{thread_id}/stream
  └── SSE stream of DeerFlow events (optional, for real-time UI)
```

---

## 五、执行流程

```
1. Human submits goal: "Deep research on LLM inference optimization techniques"
                      ↓
2. ContextBroker.dispatch(goal)
   - DeerAgent.can_handle() → True
   - Returns DispatchResult(routed_to="deer_agent", agent=DeerAgent)
                      ↓
3. Supervisor API creates pending_proposal in DB
   - type: "deer_agent"
   - goal: "Deep research on..."
   - status: "pending_approval"
                      ↓
4. Human approves via UI
                      ↓
5. Supervisor calls DeerAgent.execute(goal)
   - Creates thread_id = "deer-{uuid}"
   - DeerFlowClient.stream() runs embedded DeerFlow
   - Events streamed back (tool calls, subagent results, final text)
                      ↓
6. Results written to shared memory
   - deer_agent:{thread_id}:result → { final_text, artifacts }
                      ↓
7. Proposal marked "approved", execution "completed"
   - Human sees result in UI
```

---

## 六、配置

### DeerFlow config.yaml（DeerAgent 用）

```yaml
# DeerFlow 的标准配置，DeerAgent 直接引用
config_version: 3

models:
  - name: deepseek-v3
    display_name: DeepSeek V3
    use: deerflow.models.patched_deepseek:PatchedChatDeepSeek
    model: deepseek-reasoner
    api_key: $DEEPSEEK_API_KEY
    supports_thinking: true

  - name: claude-sonnet
    display_name: Claude Sonnet 4.6
    use: deerflow.models.claude_provider:ClaudeChatModel
    model: claude-sonnet-4-6
    supports_thinking: true

tools:
  - name: web_search
    use: deerflow.tools.web_search:TavilySearch
    api_key: $TAVILY_API_KEY
    group: web

  - name: web_fetch
    use: deerflow.tools.web_fetch:WebFetchTool
    group: web

sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider

skills:
  container_path: /path/to/deer-flow/skills
```

### SwarmMind .env 扩展

```bash
# DeerFlow 配置路径（指向 DeerFlow 的 config.yaml）
DEER_FLOW_CONFIG_PATH=/path/to/deer-flow/config.yaml

# DeerFlow skills 目录（可选，Skills 系统）
DEER_FLOW_SKILLS_PATH=/path/to/deer-flow/skills
```

---

## 七、复用策略

| DeerFlow 组件 | 复用方式 | 状态 |
|--------------|---------|------|
| `DeerFlowClient` | 直接 import，embeded 模式 | ✅ 可行 |
| Model factory (`create_chat_model`) | 参考 thinking/reasoning 配置 | ✅ 已在 LLMClient 参考 |
| Subagent 系统 | 通过 DeerFlowClient 间接使用 | ✅ 可行 |
| Tools (web search, bash, file I/O) | 通过 DeerFlow 沙盒执行 | ✅ 可行 |
| Skills system | 通过 DeerFlow 注入 system prompt | ✅ 可行 |
| Memory system | DeerFlow 内部使用，不影响 LayeredMemory | ✅ 隔离 |
| LangGraph Agent runtime | DeerFlow 内部隐藏 | ✅ 隔离 |
| Sandbox isolation | DeerFlow 内部 Docker/Kubernetes | ⚠️ 需要环境支持 |
| Gateway API | 不使用（用 SwarmMind supervisor） | ✅ 避免 |
| IM Channels | 不使用 | ✅ 避免 |

---

## 八、风险与 Mitigation

### 风险 1：DeerFlow 依赖污染

LangGraph、kubernetes 等依赖会随 `deerflow-harness` 引入。

**Mitigation：**
- 用 `pip install deerflow-harness` 作为独立 dependency
- DeerAgent 封装所有 DeerFlow 调用，其他 SwarmMind 代码不直接 import DeerFlow
- 定期检查 DeerFlow 版本，避免绑定到 internal API

### 风险 2：DeerFlow config.yaml 与 SwarmMind .env 并存

两组配置系统，增加运维复杂度。

**Mitigation：**
- DeerFlow config.yaml 放在固定路径，DeerAgent 初始化时引用
- SwarmMind 保持 .env 管理自己的配置
- 未来考虑将 DeerFlow 配置迁移到 SwarmMind 配置系统

### 风险 3：长程任务状态丢失

DeerFlow 的 checkpointing 需要配置。

**Mitigation：**
- 初始化 DeerFlowClient 时传入 checkpointer（SQLite）
- thread_id 作为持久化 key
- 任务中断后可 resume

### 风险 4：Sandbox 环境要求

生产环境需要 Docker/Kubernetes。

**Mitigation：**
- 开发环境用 `LocalSandboxProvider`
- 生产环境用 `AioSandboxProvider` + Docker
- 评估是否需要沙盒；如不需要（纯研究任务），可用 Local 模式

---

## 九、依赖

```bash
# 在 SwarmMind 项目中新增
uv add deerflow-harness

# DeerFlow 的依赖会自动带入：
# - langgraph>=1.0.6
# - langchain>=1.2.3
# - kubernetes>=30.0.0 (sandbox 用)
# - agent-sandbox>=0.0.19
# - Python>=3.12
```

---

## 十、测试计划

- [ ] `DeerFlowClient` import 和 basic chat 在 SwarmMind env 中正常
- [ ] DeerAgent 可以接收 goal 并返回结果
- [ ] 结果正确写入 shared memory
- [ ] Supervisor UI 能看到 DeerAgent 执行状态
- [ ] 多 step 任务（subagent decomposition）正确执行
- [ ] 异常情况（API key 错误、网络超时）正确处理
