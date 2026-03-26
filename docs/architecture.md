# SwarmMind 架构文档

> 版本：v0.4（草案）
> 状态：持续演进
> 调研来源：DeerFlow（bytedance）、OpenSpace（HKUDS）、OpenClaw

---

## 一、设计愿景

**SwarmMind — AI Agent 团队操作系统**

Agents 通过共享上下文协作（而非消息传递），人类监督，团队通过策略表自我演进。

**核心原则：**

- **面向接口编程，而非面向实现。** 无论 Agent 是本地 Python 进程、远程 HTTP 服务、还是独立容器，都通过统一的 Agent Interface 接入。
- **Context Broker 只认 Interface，不关心背后是什么框架。**

**三方调研结论：**

- **DeerFlow** 的优势：多 Agent 编排、Skills 格式、Execution Recording、Memory injection
- **OpenSpace** 的优势：自进化技能引擎、Token 效率、群体智能（可 import 作为执行引擎）
- **OpenClaw** 的优势：本地 AI 助手，通过 Gateway HTTP API 暴露能力（典型远程 Agent）

---

## 二、核心架构

### 2.1 完整架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     Human Supervisor                             │
│               (审批 / 策略配置 / 干预)                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Context Broker                             │
│         dispatch() → 路由 → Agent Interface → Agent             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Interface                               │
│                  (统一抽象层，所有 Agent 的标准接入点)              │
└──────────┬──────────────┬──────────────┬───────────────────────┘
           │              │              │
     ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
     │   Local   │ │  Remote   │ │    MCP    │
     │  Adapter  │ │  Adapter  │ │  Adapter  │
     └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
           │              │              │
     ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
     │ DeferFlow │ │ OpenSpace │ │ OpenClaw  │
     │ OpenSpace │ │  (HTTP)   │ │ (HTTP)    │
     │ LangGraph │ │  nanobot  │ │  任意     │
     │  任意     │ │  容器     │ │  HTTP Agent│
     └───────────┘ └───────────┘ └───────────┘
```

### 2.2 Agent Interface 分层

```
Context Broker
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Interface                               │
│                      (ABC)                                       │
├─────────────────────────────────────────────────────────────────┤
│  @property name: str                                             │
│  @property supported_domains: list[str]                         │
│  @property adapter_type: AdapterType  (LOCAL / REMOTE)           │
│  async execute(goal, context, max_iterations) → AgentResponse   │
│  async execute_stream(...) → AsyncIterator[AgentResponse]        │
│  async get_status(task_id) → str | None                          │
│  async cancel(task_id) → bool                                    │
│  async list_models() / list_skills() / upload_files() (可选)     │
└─────────────────────────────────────────────────────────────────┘
           │
    ┌──────┴──────────────────────────────────────┐
    │                                             │
    ▼                                             ▼
┌───────────────┐                    ┌───────────────────────────┐
│ Local Adapter │                    │      Remote Adapter        │
│ (进程内 import)│                    │  (HTTP / MCP / ... )      │
├───────────────┤                    ├───────────────────────────┤
│ DeferFlow     │                    │ OpenClaw Gateway (HTTP)   │
│ OpenSpace     │                    │ nanobot (HTTP / MCP)      │
│ LangGraph     │                    │ Claude Code (MCP)         │
│ 自定义 Python │                    │ 任意 HTTP Agent            │
│  (import)     │                    │ Docker 容器                │
└───────────────┘                    └───────────────────────────┘

注：MCP 是 Agent 自身的工具协议，不是一种 Adapter 类型。
    支持 MCP 的远程 Agent（如 Claude Code）通过 Remote Adapter 接入，
    通信协议为 MCP，但 Adapter 类型仍为 REMOTE。
```

---

## 三、LayeredMemory 四层记忆系统

### 3.1 核心设计

LayeredMemory 是 SwarmMind 的共享上下文基础设施，**替代了扁平的 KV store**，提供：

- **作用域隔离**：不同粒度的数据互不污染
- **TTL 支持**：临时数据自动过期
- **会话晋升**：L1 的有效数据可晋升到 L2/L3 持久化
- **CAS 语义**：避免并发写入冲突

### 3.2 四层结构

| 层 | 名称 | 作用域 | 用途 | TTL |
|---|------|--------|------|-----|
| **L1** | TMP | session_id | 临时会话数据 | 24h（默认） |
| **L2** | TEAM | team_id | 团队共享记忆 | 无 |
| **L3** | PROJECT | project_id | 项目上下文 | 无 |
| **L4** | USER_SOUL | user_id | 用户特质，全局唯一，只读 | 无 |

**读优先级**：L1 > L2 > L3 > L4（更具体的层覆盖更抽象的层）

```
User (L4 USER_SOUL)
     │
Project (L3 PROJECT)
     │
Team (L2 TEAM) ← 多个 Role 共享同一个 Team 的 LayeredMemory scope
     │
Session (L1 TMP) ← 一次交互的上下文
```

### 3.3 Team 与 LayeredMemory 的关系

```
Team: software-team
├── Role: ui-designer      → L2/TEAM/{team_id} 写入设计上下文
├── Role: backend-dev      → L2/TEAM/{team_id} 读取设计上下文
├── Role: frontend-dev     → L2/TEAM/{team_id} 读取设计上下文
└── Role: qa-tester        → L2/TEAM/{team_id} 读取设计上下文

所有 Role 共享同一个 team_id scope：
  ui-designer 写入 "design:login-page" → L2/TEAM/software-team
  frontend-dev 读取 "design:login-page" → 获得设计上下文
```

### 3.4 关键行为

**写入授权**：
- L4（USER_SOUL）只有 `SOUL_WRITER_AGENT_IDS` 中的 agent 才能写入
- 普通 agent 尝试写 L4 会抛出 `MemoryWriteForbidden`

**TTL 行为**：
- L1 默认 24h TTL，上限 7 天
- L2/L3/L4 无 TTL
- TTL 在读取时惰性检查

**CAS 协议**：
- `write()` 可选 `expected_version` 参数实现 CAS 语义
- 无 `expected_version` 时使用 last-write-wins + 3x 重试

**会话晋升（Session Promotion）**：
- `promote_session(session_id, target_scope, key_filter)` 将 L1 数据迁移到 L2/L3
- 创建晋升记录，不删除源数据（Phase 2）

### 3.5 数据库 Schema

```sql
CREATE TABLE memory_entries (
    id              TEXT PRIMARY KEY,
    layer           TEXT NOT NULL,   -- 'L1_tmp', 'L2_team', 'L3_project', 'L4_user_soul'
    scope_id        TEXT NOT NULL,   -- session_id / team_id / project_id / user_id
    key             TEXT NOT NULL,
    value           TEXT NOT NULL,
    tags            TEXT,            -- JSON array
    ttl             INTEGER,         -- seconds（仅 L1）
    version         INTEGER DEFAULT 1,
    last_writer_agent_id TEXT,
    UNIQUE(layer, scope_id, key)
);

CREATE TABLE session_promotions (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    target_layer    TEXT NOT NULL,
    target_scope_id TEXT NOT NULL,
    key_filter      TEXT,            -- JSON array
    snapshot_count  INTEGER DEFAULT 0
);
```

### 3.6 与 Agent Adapter 的集成

所有 Adapter 执行后的结果写入 `ExecutionContext` 对应的 LayeredMemory scope：

```python
class AgentAdapter(ABC):
    async def execute(self, goal, context: ExecutionContext, ...) -> AgentResponse:
        # 执行完成后，结果写入对应的 LayeredMemory scope
        scope = self._resolve_write_scope(context)
        self._memory.write(scope=scope, key=f"result:{task_id}", value=result)
        return response
```

---

## 四、Agent Interface 定义

### 3.1 核心类型

```python
# swarmmind/agents/adapters/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator
import uuid

class AdapterType(Enum):
    LOCAL = "local"    # 进程内 import 调用
    REMOTE = "remote"  # HTTP / MCP 等远程协议调用

@dataclass
class AgentResponse:
    """标准化响应格式，所有 Adapter 必须返回此格式"""
    status: str                      # "success" | "failure" | "partial"
    result: str                      # 执行结果文本
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skills_evolved: list[dict] = field(default_factory=list)  # Phase 3
    recordings: list[str] = field(default_factory=list)        # Phase 3
    metadata: dict[str, Any] = field(default_factory=dict)     # 框架特定信息

    # 流式支持（Phase 2+）
    is_stream: bool = False
    stream_content: str = ""        # 增量内容（流式时累加）

@dataclass
class ExecutionContext:
    """传递给 Adapter 的上下文信息"""
    session_id: str | None = None
    team_id: str | None = None
    project_id: str | None = None
    user_id: str = "default_user"
    visible_scopes: list[str] = field(default_factory=list)  # LayeredMemory scopes
    metadata: dict[str, Any] = field(default_factory=dict)

class AgentAdapter(ABC):
    """
    所有 Agent 框架的统一接口。

    Context Broker 只认这个 Interface，不关心背后是：
    - OpenSpace（import，Local）
    - DeerFlow（import，Local）
    - OpenClaw（HTTP，Remote）
    - nanobot（HTTP，Remote）
    - 用户自定义 LangGraph（import，Local）
    - 未来任何新框架
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Adapter 唯一名称"""
        ...

    @property
    @abstractmethod
    def adapter_type(self) -> AdapterType:
        """Adapter 类型：LOCAL / REMOTE / MCP"""
        ...

    @property
    @abstractmethod
    def supported_domains(self) -> list[str]:
        """
        此 Adapter 支持的领域标签。
        返回 ["*"] 表示支持所有领域。
        """
        ...

    @abstractmethod
    async def execute(
        self,
        goal: str,
        context: ExecutionContext | None = None,
        max_iterations: int | None = None,
    ) -> AgentResponse:
        """
        执行一个目标。Phase 1: 同步等待结果。

        Args:
            goal: 要执行的目标描述
            context: 执行上下文（session、team、project 等）
            max_iterations: 最大迭代次数限制

        Returns:
            AgentResponse: 标准化响应
        """
        ...

    @abstractmethod
    async def execute_stream(
        self,
        goal: str,
        context: ExecutionContext | None = None,
    ) -> AsyncIterator[AgentResponse]:
        """
        流式执行，Phase 2+ 使用。
        用于需要实时展示进度的场景（如 Supervisor UI 流式输出）。

        Yields:
            AgentResponse: 增量响应片段，is_stream=True
        """
        ...

    async def get_status(self, task_id: str) -> str | None:
        """
        查询任务状态。如果 Adapter 不支持，返回 None。

        Returns:
            "pending" | "running" | "success" | "failure" | "cancelled"，不支持时返回 None
        """
        return None

    async def cancel(self, task_id: str) -> bool:
        """
        取消正在执行的任务。如果 Adapter 不支持，返回 False。

        Returns:
            True if cancelled, False if not supported
        """
        return False

    async def health_check(self) -> bool:
        """健康检查。默认返回 True（假设进程内 Adapter 都健康）。"""
        return True

    # ------------------------------------------------------------------
    # DeerFlow 兼容所需的方法（Adapter 可选实现）
    # ------------------------------------------------------------------

    async def list_models(self) -> dict | None:
        """
        列出可用模型（DeerFlow 兼容）。
        返回 None 表示不支持。
        """
        return None

    async def list_skills(self, enabled_only: bool = False) -> dict | None:
        """
        列出可用技能（DeerFlow 兼容）。
        返回 None 表示不支持。
        """
        return None

    async def upload_files(self, thread_id: str, files: list[str]) -> dict | None:
        """
        上传文件到线程（DeerFlow 兼容）。
        返回 None 表示不支持。
        """
        return None
```

### 3.2 AgentRegistry：管理所有 Adapter

```python
# swarmmind/agents/adapters/registry.py

from typing import Optional

class AgentRegistry:
    """
    管理所有注册的 Agent Adapter。
    Context Broker 通过此 Registry 选择合适的 Adapter。
    """

    def __init__(self):
        self._adapters: dict[str, AgentAdapter] = {}
        self._default_adapter: str | None = None

    def register(
        self,
        adapter: AgentAdapter,
        set_as_default: bool = False,
    ) -> None:
        """注册一个 Adapter"""
        self._adapters[adapter.name] = adapter
        if set_as_default or not self._default_adapter:
            self._default_adapter = adapter.name

    def unregister(self, name: str) -> None:
        """注销一个 Adapter"""
        if name in self._adapters:
            del self._adapters[name]
        if self._default_adapter == name:
            self._default_adapter = next(iter(self._adapters), None)

    def get(self, name: str) -> AgentAdapter | None:
        return self._adapters.get(name)

    def list_adapters(self) -> list[str]:
        return list(self._adapters.keys())

    def select(
        self,
        situation_tag: str,
        preferred_adapter: str | None = None,
    ) -> AgentAdapter:
        """
        根据 situation_tag 选择最合适的 Adapter。

        Phase 1: 简单配置指定或轮询
        Phase 2+: 看 quality metrics 选最好的

        Args:
            situation_tag: 场景标签（如 "finance", "code_review"）
            preferred_adapter: 优先使用的 adapter 名称（覆盖自动选择）

        Returns:
            选中的 Adapter 实例
        """
        # 优先使用指定的 adapter
        if preferred_adapter and preferred_adapter in self._adapters:
            return self._adapters[preferred_adapter]

        # 精确匹配 domain
        for adapter in self._adapters.values():
            if situation_tag in adapter.supported_domains:
                return adapter

        # 通配匹配
        for adapter in self._adapters.values():
            if "*" in adapter.supported_domains:
                return adapter

        # 使用默认
        if self._default_adapter:
            return self._adapters[self._default_adapter]

        raise ValueError(f"No adapter available for situation_tag={situation_tag}")
```

---

## 五、Adapter 实现

### 4.1 Local Adapter（进程内调用）

适用于直接 import 的 Python 包：OpenSpace、DeerFlow、用户自定义 Agent。

```python
# swarmmind/agents/adapters/local_adapter.py

from dataclasses import dataclass
from typing import Any

from swarmmind.agents.adapters.base import (
    AgentAdapter,
    AgentResponse,
    AdapterType,
    ExecutionContext,
)
from swarmmind.config import LLM_MODEL

@dataclass
class LocalAdapterConfig:
    import_path: str          # 如 "openspace", "deerflow.client"
    class_name: str          # 如 "OpenSpace", "DeerFlowClient"
    init_kwargs: dict[str, Any] = None
    execute_method: str = "execute"  # 调用的方法名
    stream_method: str = "execute_stream"  # 流式方法名


class LocalAgentAdapter(AgentAdapter):
    """
    接入进程内的 Python Agent 框架。
    通过 importlib 动态加载，不直接依赖具体框架包。
    """

    def __init__(self, name: str, config: LocalAdapterConfig):
        self._name = name
        self._config = config
        self._instance = self._load_and_init()

    @property
    def name(self) -> str:
        return self._name

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.LOCAL

    @property
    def supported_domains(self) -> list[str]:
        return self._config.supported_domains

    def _load_and_init(self):
        import importlib
        module = importlib.import_module(self._config.import_path)
        cls = getattr(module, self._config.class_name)
        return cls(**(self._config.init_kwargs or {}))

    async def execute(self, goal, context=None, max_iterations=None) -> AgentResponse:
        method = getattr(self._instance, self._config.execute_method)
        result = await method(goal, context=context, max_iterations=max_iterations)
        return self._normalize_response(result)

    async def execute_stream(self, goal, context=None) -> AgentResponse:
        method = getattr(self._instance, self._config.stream_method)
        async for chunk in method(goal, context=context):
            yield self._normalize_response(chunk)

    async def get_status(self, task_id: str) -> str:
        # 本地 Agent 通常是同步的，没有 task_id 概念
        return "success"

    async def cancel(self, task_id: str) -> None:
        pass  # 本地 Agent 不支持取消

    def _normalize_response(self, raw: Any) -> AgentResponse:
        # 将框架原生响应格式转为 AgentResponse
        # 具体实现取决于框架接口
        ...
```

### 4.2 Remote Adapter（HTTP API 调用）

适用于独立运行的 Agent 服务：OpenClaw Gateway、nanobot HTTP API、Docker 容器。

```python
# swarmmind/agents/adapters/remote_adapter.py

import httpx
from dataclasses import dataclass

from swarmmind.agents.adapters.base import (
    AgentAdapter,
    AgentResponse,
    AdapterType,
    ExecutionContext,
)

@dataclass
class RemoteAdapterConfig:
    base_url: str                    # 如 "http://localhost:18789"
    api_key: str | None = None      # 认证密钥
    timeout: float = 300.0           # 请求超时（秒）
    supported_domains: list[str] = field(default_factory=["*"])

    # HTTP 端点配置
    execute_endpoint: str = "/execute"
    status_endpoint: str = "/status/{task_id}"
    cancel_endpoint: str = "/cancel/{task_id}"
    health_endpoint: str = "/health"


class RemoteAgentAdapter(AgentAdapter):
    """
    通过 HTTP API 接入远程 Agent。

    典型场景：
    - OpenClaw Gateway (http://localhost:18789)
    - nanobot HTTP API
    - Docker 容器内的 Agent
    - 任意提供 HTTP API 的 Agent 服务
    """

    def __init__(self, name: str, config: RemoteAdapterConfig):
        self._name = name
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=httpx.Timeout(config.timeout),
            headers={"Authorization": f"Bearer {config.api_key}"} if config.api_key else {},
        )
        self._running_tasks: dict[str, str] = {}  # task_id -> adapter_task_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def adapter_type(self) -> AdapterType:
        return AdapterType.REMOTE

    @property
    def supported_domains(self) -> list[str]:
        return self._config.supported_domains

    async def execute(
        self,
        goal: str,
        context: ExecutionContext | None = None,
        max_iterations: int | None = None,
    ) -> AgentResponse:
        """通过 HTTP POST 调用远程 Agent"""
        payload = {
            "goal": goal,
            "context": context.metadata if context else {},
            "max_iterations": max_iterations,
        }

        response = await self._client.post(
            self._config.execute_endpoint,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return AgentResponse(
            status=data.get("status", "success"),
            result=data.get("result", ""),
            task_id=data.get("task_id", ""),
            skills_evolved=data.get("skills_evolved", []),
            recordings=data.get("recordings", []),
            metadata={
                "framework": "remote",
                "adapter": self._name,
                "raw_response": data,
            },
        )

    async def execute_stream(
        self,
        goal: str,
        context: ExecutionContext | None = None,
    ) -> AgentResponse:
        """通过 HTTP SSE 流式调用远程 Agent"""
        payload = {
            "goal": goal,
            "context": context.metadata if context else {},
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            self._config.execute_endpoint,
            json=payload,
        ) as response:
            response.raise_for_status()
            accumulated = ""

            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = json.loads(line[5:])
                    accumulated += data.get("content", "")
                    yield AgentResponse(
                        status="running",
                        result=accumulated,
                        is_stream=True,
                        stream_content=data.get("content", ""),
                    )

    async def get_status(self, task_id: str) -> str:
        url = self._config.status_endpoint.format(task_id=task_id)
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json().get("status", "unknown")

    async def cancel(self, task_id: str) -> None:
        url = self._config.cancel_endpoint.format(task_id=task_id)
        await self._client.post(url)

    async def health_check(self) -> bool:
        """检查远程 Agent 是否可达"""
        try:
            response = await self._client.get(self._config.health_endpoint)
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self._client.aclose()
```

---

## 六、Team 与 Role 系统

### 5.1 第一性原理

**Team 的本质：弥补单个 Agent 能力不足而存在。**

当一个目标需要多种专业能力时，单个 Agent 无法覆盖，必须由多个专业角色协作完成。

```
Goal: 制作一个软件
         ↓
需要多种能力，单个 Agent 无法覆盖：
 ┌─────────────────────────────────────────────────┐
 │  UI 设计    → 需要设计 Agent                     │
 │  产品管理   → 需要规划 Agent                     │
 │  前端开发   → 需要代码 Agent                     │
 │  后端开发   → 需要代码 Agent                     │
 │  测试验证   → 需要验证 Agent                     │
 └─────────────────────────────────────────────────┘
         ↓
     协作完成同一目标
```

**关键洞察：Team 里的"角色"和 Agent Adapter 是不同层次的概念。**

| 层次 | 实体 | 职责 |
|------|------|------|
| SwarmMind 层 | Agent Adapter | 执行引擎（DeerFlow / OpenSpace / OpenJarvis） |
| Team 层 | Role（角色） | 完成目标的某方面能力（UI/后端/测试） |
| Context Broker 层 | Router | 把 goal 路由到正确的 Role |

**一个 Agent Adapter 可以同时担任多个 Role。**

### 5.2 核心类型定义

```python
# swarmmind/teams/types.py

from dataclasses import dataclass, field
from typing import Any

@dataclass
class Role:
    """
    Team 中的角色定义。
    一个 Role 绑定到一个 Agent Adapter，由该 Adapter 的执行引擎提供能力。
    """
    name: str                          # 角色名："ui-designer", "backend-dev"
    adapter_name: str                 # 绑定的 Adapter 名称："openjarvis-react", "openspace"
    agent_type: str | None = None    # Adapter 内部的 agent 类型（OpenJarvis 用）
    description: str = ""            # 角色描述
    min_instances: int = 1           # 最少实例数（1 = 无冗余）
    max_instances: int = 1           # 最多实例数（>1 = 可冗余执行）
    capabilities: list[str] = field(default_factory=list)  # 能力标签

    def matches_situation(self, situation_tag: str) -> bool:
        """检查此角色是否适合处理给定场景"""
        return situation_tag in self.capabilities


@dataclass
class Team:
    """
    Team 是角色的集合，共享同一个 LayeredMemory scope。
    Team 是目标导向的——为完成特定类型的任务而存在。
    """
    id: str
    name: str
    description: str = ""
    roles: list[Role] = field(default_factory=list)
    shared_scope_layer: str = "TEAM"   # LayeredMemory 的 L2 TEAM 层
    strategy_table: dict[str, float] = field(default_factory=dict)  # 成功率追踪

    def get_role(self, role_name: str) -> Role | None:
        return next((r for r in self.roles if r.name == role_name), None)

    def get_role_for_situation(self, situation_tag: str) -> Role | None:
        """根据场景标签找到最合适的 Role"""
        for role in self.roles:
            if role.matches_situation(situation_tag):
                return role
        return None


@dataclass
class TeamInstance:
    """
    Team 的运行时实例。
    同一个 Team 定义可以同时存在多个 Instance（不同的 session_id）。
    """
    team_id: str
    instance_id: str                  # 通常是 session_id
    roles: dict[str, str] = field(default_factory=dict)  # role_name -> adapter_name
    shared_context_scope: MemoryScope  # 共享的 LayeredMemory scope
    status: str = "active"           # active / paused / completed
```

### 5.3 Team 协作流程

```
用户目标: "设计并实现一个登录页面"
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│                    Context Broker                            │
│  解析目标 → 发现需要 software-team → Team Orchestrator      │
└──────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────┐
│                  Team Orchestrator                          │
│  1. 分解目标为 sub-goals（规划阶段）                        │
│  2. 路由到具体 Role                                         │
│  3. 收集结果，合并到共享 LayeredMemory                       │
│  4. 追踪团队状态                                             │
└──────────────────────────────────────────────────────────────┘
              │
    ┌─────────┼─────────┬─────────┐
    ▼         ▼         ▼         ▼
 ui-design  backend   frontend    qa
    │         │         │         │
    │         └─────────┼─────────┘
    │                   │
    ▼                   ▼
 LayeredMemory (共享设计上下文)
```

### 5.4 Team 与 Adapter 的关系

```
Team: software-team
├── Role: ui-designer
│   └── Adapter: OpenJarvis(agent_type="react") — 提供 UI 设计能力
├── Role: backend-dev
│   └── Adapter: OpenSpace — 提供后端执行能力
├── Role: frontend-dev
│   └── Adapter: OpenJarvis(agent_type="openhands") — 提供前端开发能力
└── Role: qa-tester
    └── Adapter: OpenSpace — 提供测试执行能力

同一个 Adapter 实例可以担任多个 Role：
  OpenJarvis(react) 可以同时是 ui-designer 和 frontend-dev
  OpenSpace 可以同时是 backend-dev 和 qa-tester
```

### 5.5 Team 定义示例

```python
# 预定义的 software-team
SOFTWARE_TEAM = Team(
    id="software-team",
    name="Software Development Team",
    description="端到端软件开发生命周期团队",
    roles=[
        Role(
            name="product-manager",
            adapter_name="deerflow",
            description="产品规划和需求分析",
            capabilities=["planning", "requirements", "analysis"],
        ),
        Role(
            name="ui-designer",
            adapter_name="openjarvis-react",
            agent_type="react",
            description="用户界面设计",
            capabilities=["ui-design", "frontend", "visual"],
        ),
        Role(
            name="backend-dev",
            adapter_name="openspace",
            description="后端服务开发",
            capabilities=["backend", "api", "database"],
        ),
        Role(
            name="frontend-dev",
            adapter_name="openjarvis-react",
            agent_type="react",
            description="前端应用开发",
            capabilities=["frontend", "react", "javascript"],
        ),
        Role(
            name="qa-tester",
            adapter_name="openspace",
            description="质量保证和测试",
            capabilities=["testing", "qa", "validation"],
        ),
    ],
    shared_scope_layer="TEAM",
)
```

---

## 七、Context Broker 与 Agent Interface 的集成

### 6.1 重构后的 Context Broker

```python
# swarmmind/context_broker/broker.py

from swarmmind.agents.adapters.registry import AgentRegistry
from swarmmind.agents.adapters.base import (
    AgentAdapter,
    AgentResponse,
    ExecutionContext,
)
from swarmmind.models import DispatchResponse, MemoryContext

class ContextBroker:
    """
    目标路由核心。
    Phase 1: 关键词路由 + AgentRegistry
    Phase 2+: Embedding 路由 + SkillRegistry
    """

    def __init__(
        self,
        agent_registry: AgentRegistry,
        # Phase 2+:
        # skill_registry: SkillRegistry | None = None,
    ):
        self._agent_registry = agent_registry

    async def dispatch(
        self,
        goal: str,
        user_id: str = "default_user",
        project_id: str | None = None,
        team_id: str | None = None,
        session_id: str | None = None,
        override_situation_tag: str | None = None,
        preferred_agent: str | None = None,
    ) -> DispatchResponse:
        """
        路由入口。
        1. 解析 situation_tag
        2. 从 AgentRegistry 选择 Adapter
        3. 调用 Adapter.execute()
        4. 返回结果
        """
        situation_tag = override_situation_tag or self._derive_situation_tag(goal)

        adapter = self._agent_registry.select(
            situation_tag=situation_tag,
            preferred_adapter=preferred_agent,
        )

        ctx = ExecutionContext(
            user_id=user_id,
            project_id=project_id,
            team_id=team_id,
            session_id=session_id,
        )

        response = await adapter.execute(goal, context=ctx)

        return DispatchResponse(
            action_proposal_id=response.task_id,
            agent_id=adapter.name,
            status="success" if response.status == "success" else "failure",
            memory_ctx=MemoryContext(...),
        )

    def _derive_situation_tag(self, goal: str) -> str:
        # Phase 1: 关键词路由
        # Phase 2+: embedding 相似度
        ...
```

### 5.2 启动时注册 Adapter

```python
# swarmmind/main.py 或启动逻辑

from swarmmind.agents.adapters.registry import AgentRegistry
from swarmmind.agents.adapters.local_adapter import LocalAgentAdapter, LocalAdapterConfig
from swarmmind.agents.adapters.remote_adapter import RemoteAgentAdapter, RemoteAdapterConfig

def setup_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()

    # === Local Adapters ===

    # OpenSpace（import，Local）
    registry.register(
        LocalAgentAdapter(
            name="openspace",
            config=LocalAdapterConfig(
                import_path="openspace",
                class_name="OpenSpace",
                init_kwargs={"llm_model": "anthropic/claude-sonnet-4-5"},
                supported_domains=["*"],  # 通用执行引擎
            ),
        )
    )

    # DeerFlow（import，Local）
    registry.register(
        LocalAgentAdapter(
            name="deerflow",
            config=LocalAdapterConfig(
                import_path="deerflow.client",
                class_name="DeerFlowClient",
                supported_domains=["research", "analysis", "general"],
            ),
        )
    )

    # 用户自定义 LangGraph（import，Local）
    registry.register(
        LocalAgentAdapter(
            name="my-langgraph",
            config=LocalAdapterConfig(
                import_path="my_agents.finance_graph",
                class_name="CompiledGraph",
                supported_domains=["finance"],
            ),
        )
    )

    # === Remote Adapters ===

    # OpenClaw Gateway（HTTP，Remote）
    registry.register(
        RemoteAgentAdapter(
            name="openclaw",
            config=RemoteAdapterConfig(
                base_url="http://localhost:18789",
                supported_domains=["*"],  # OpenClaw 是通用助手
            ),
        ),
        set_as_default=True,  # 可设为默认
    )

    # nanobot（HTTP，Remote）
    registry.register(
        RemoteAgentAdapter(
            name="nanobot",
            config=RemoteAdapterConfig(
                base_url="http://localhost:8080",
                api_key=os.environ.get("NANOBOT_API_KEY"),
                supported_domains=["code", "review", "general"],
            ),
        )
    )

    return registry
```

---

## 八、演进路线图

```
Phase 1          Phase 2              Phase 3              Phase 4
(当前)          (Agent Interface)   (技能系统)          (群体智能)
  │                │                   │                    │
  ▼                ▼                   ▼                    ▼
关键词路由     Agent Interface      技能注册表         云端技能社区
固定Agent       Local/Remote/MCP    三阶段选择管线       跨团队共享
人类审批       统一抽象层           自进化触发器
                                                  Agent 也可远程部署
```

---

## 九、关键设计决策

### 7.1 Interface 隔离，框架解耦

Context Broker 只认 `AgentAdapter` Interface。换成任何框架都不需要修改 Context Broker。

### 7.2 Remote Agent 是第一等公民

OpenClaw、nanobot 等远程 Agent 和本地 import 的 Agent 享有同等地位。REMOTE Adapter 通过 HTTP 接入，包含健康检查机制。

### 7.3 共享上下文是核心

所有 Adapter 执行后的结果写入 LayeredMemory。Agent 之间通过共享上下文协作，而非消息传递。

### 7.4 人类监督贯穿全程

- Phase 1: 人类审批每个 ActionProposal
- Phase 2+: 人类可以配置哪些 Adapter 需要审批
- Adapter 执行结果反馈到策略表

### 7.5 避免重型框架耦合

不引入 LangGraph 作为核心依赖。Skills 作为 prompt 片段注入，MCP 集成保持可选。

---

## 十、文件结构（Phase 2 目标）

```
swarmmind/
├── __init__.py
├── config.py
├── llm.py
├── db.py
├── models.py
│
├── context_broker/
│   ├── __init__.py
│   ├── broker.py          # ContextBroker 主类
│   ├── router.py         # 路由逻辑（Phase 2: embedding）
│   └── strategy_table.py  # 策略表管理
│
├── agents/
│   ├── __init__.py
│   ├── base.py           # 过渡保留（Phase 1 的 BaseAgent）
│   │
│   └── adapters/          # [Phase 2 核心新增]
│       ├── __init__.py
│       ├── base.py        # AgentAdapter ABC + AgentResponse
│       ├── registry.py    # AgentRegistry
│       │
│       ├── local_adapter.py    # LocalAgentAdapter
│       ├── remote_adapter.py  # RemoteAgentAdapter
│       │
│       └── configs/            # Adapter 配置
│           ├── openspace_config.py
│           ├── deerflow_config.py
│           ├── openclaw_config.py
│           └── ...
│
├── skills/                 # [Phase 3 新增]
│   ├── registry.py
│   ├── store.py
│   ├── types.py
│   ├── ranker.py
│   ├── analyzer.py
│   ├── evolver.py
│   ├── recorder.py
│   └── built_in/
│
├── memory/
│   ├── layered_memory.py
│   └── shared_memory.py
│
├── cloud/                  # [Phase 4 新增]
│   ├── client.py
│   ├── search.py
│   └── sync.py
│
├── grounding/              # [Phase 2 参考 DeerFlow]
│   ├── __init__.py
│   ├── shell.py
│   ├── mcp.py
│   └── tools.py
│
├── api/
│   └── supervisor.py
│
└── ui/
```

---

## 十一、与外部项目的定位对比

| | SwarmMind | DeerFlow | OpenSpace | OpenClaw |
|---|---|---|---|---|
| **核心抽象** | Agent Interface + 共享上下文 | LangGraph 多 Agent 编排 | 自进化技能（可 import） | 本地 AI 助手（HTTP Gateway） |
| **接入方式** | Interface 标准 | import | import | HTTP API |
| **部署形态** | 本地服务 | 进程内 | 进程内 | 独立进程/容器 |
| **协作模型** | Context Broker 路由 + 共享内存 | LangGraph 状态机 | 技能共享 | 单 Agent |
| **多 Agent** | Context Broker（轻量） | LangGraph（重型） | 无 | 无 |
| **人类监督** | Supervisor UI（核心） | 无 | 无 | 无 |
| **自进化** | Phase 3 引入 | 无 | 有 | 无 |

---

## 十二、开放问题

1. **Remote Agent 的生命周期管理**
   - OpenClaw 等远程 Agent 如何启动/停止？
   - SwarmMind 是否负责管理这些进程的生死？

2. **Remote Adapter 的健康检查频率**
   - 多久检查一次远程 Agent 是否存活？
   - 不可用时如何降级？

3. **Adapter 级别的认证和限流**
   - 不同 Adapter 可能有不同的 API Key、限流策略
   - 如何统一管理？

4. **Phase 2 的 Finance Agent / Code Review Agent 如何迁移？**
   - 选项 A：保留为 Local Adapter，内部委托给 SkillExecutor
   - 选项 B：完全废弃，Adapter 替代
