# DeerFlow 调研报告

> 调研时间：2026-03-23
> 仓库：https://github.com/bytedance/deer-flow

## 一、架构概览

```
Client (Browser)
      │
      ▼
Nginx (Port 2026)
  ├── /api/langgraph/* → LangGraph Server (2024)
  ├── /api/*           → Gateway API  (8001)
  └── /*               → Frontend     (3000)
```

**核心组件：**

- **LangGraph Server** — agent 运行时，基于 LangGraph 的多 agent 编排，streaming SSE
- **Gateway API** — FastAPI，提供 models、MCP、skills、memory 等 REST 端点
- **Frontend** — Next.js + Radix UI（**不是 shadcn/ui**）
- **deerflow-harness** — `backend/packages/harness/deerflow/` — 核心可复用 Python 包

**本地目录：** `/tmp/deer-flow`

---

## 二、可复用性分析

### 1. `DeerFlowClient` — 最值得复用 ⭐

**路径：** `backend/packages/harness/deerflow/client.py`

```python
from deerflow.client import DeerFlowClient

client = DeerFlowClient()
response = client.chat("Analyze this paper", thread_id="my-thread")

# Streaming
for event in client.stream("hello"):
    print(event.type, event.data)

# 配置查询
client.list_models()
client.list_skills()
client.get_memory()
```

**特点：**
- 纯 Python embedding client，**不需要启动任何 server 进程**
- 支持 streaming、multi-turn（需 checkpointer）、model override
- API 简洁：`chat()`、`stream()`、`list_models()`、`list_skills()`、`get_memory()`
- Lazy agent 创建，配置变更后调用 `reset_agent()` 刷新

**复用可行性：最高**。可以作为 SwarmMind 的"agent 执行引擎"，直接 import 使用。

---

### 2. Model Factory — `models/factory.py`

**路径：** `backend/packages/harness/deerflow/models/factory.py`

`create_chat_model()` 统一创建多 provider 模型：

- OpenAI (`langchain_openai:ChatOpenAI`)
- Anthropic (`langchain_anthropic:ChatAnthropic`)
- DeepSeek (`deerflow.models.patched_deepseek:PatchedChatDeepSeek`)
- Codex CLI (`deerflow.models.openai_codex_provider:CodexChatModel`)
- Claude Code OAuth (`deerflow.models.claude_provider:ClaudeChatModel`)
- Google Gemini (`langchain_google_genai:ChatGoogleGenerativeAI`)

**支持的功能：**

- thinking/reasoning_effort 模式配置
- use_responses_api（OpenAI Responses API）
- LangSmith tracing 集成
- per-model vision support 检测

**复用可行性：高**。SwarmMind 已有自己的 `llm.py`，但 model factory 的 thinking/reasoning 配置策略可参考。

---

### 3. Tools 系统 — `sandbox/tools.py`

**路径：** `backend/packages/harness/deerflow/sandbox/tools.py`

沙盒隔离的 tool 执行，支持：

- `bash`、`read_file`、`write_file`、`str_replace_based_edit`、`ls`、`glob`
- Web search (`tavily`、`firecrawl`、`ddgs duck search`)
- 路径安全检查、虚拟路径映射 (`/mnt/user-data/workspace` → `~/.deer-flow/threads/{thread_id}/...`)
- Skills container path 注入 (`/mnt/skills`)

**Tool 加载机制：**

```python
from deerflow.tools import get_available_tools

tools = get_available_tools(
    groups=["web"],           # 按 group 过滤
    include_mcp=True,         # 包含 MCP tools
    model_name="gpt-4",       # vision model 检测
    subagent_enabled=False,
)
```

**复用可行性：中**。SwarmMind 的 agent 目前没有沙盒隔离，直接复用需要引入 `agent-sandbox` 和 Docker 依赖。

---

### 4. Memory System — `agents/memory/`

**路径：** `backend/packages/harness/deerflow/agents/memory/`

结构化 memory 存储：

```python
{
    "version": "1.0",
    "lastUpdated": "2024-01-15T10:30:00Z",
    "user": {
        "workContext": {"summary": "...", "updatedAt": "..."},
        "personalContext": {"summary": "...", "updatedAt": "..."},
        "topOfMind": {"summary": "...", "updatedAt": "..."}
    },
    "history": {
        "recentMonths": {"summary": "...", "updatedAt": "..."},
        "earlierContext": {"summary": "...", "updatedAt": "..."},
        "longTermBackground": {"summary": "...", "updatedAt": "..."}
    },
    "facts": [
        {"id": "...", "content": "...", "category": "context", "confidence": 0.85, "source": "thread_123"}
    ]
}
```

**特点：**

- 基于 tiktoken 的准确 token counting
- LLM 生成 memory update（`updater.py`）
- Per-agent memory 隔离
- 文件 mtime 缓存失效机制
- **计划中（未合并）：** TF-IDF similarity-based fact retrieval

**复用可行性：中**。SwarmMind 已有 4 层 `LayeredMemory`，但 DeerFlow 的 memory injection 策略（token budget、confidence ranking）值得参考。

---

### 5. Skills System — `skills/loader.py`

**路径：** `backend/packages/harness/deerflow/skills/loader.py`

SKILL.md 格式：

```markdown
---
name: deep-research
description: Use this skill for web research tasks
license: MIT
allowed-tools:
  - bash
  - web_search
---

# Deep Research Skill

## When to Use This Skill
...
```

**内置 Skills（17 个）：**

- `deep-research` — 系统化多角度网络研究
- `frontend-design` — 前端设计技能
- `data-analysis` — 数据分析
- `github-deep-research` — GitHub 代码研究
- `ppt-generation`、`video-generation`、`podcast-generation` — 多媒体生成
- `skill-creator` — 创建新 skill
- 等

**复用可行性：中**。Skills 作为 system prompt 片段注入 agent。SwarmMind 没有 skill 系统，如需可考虑借用。

---

### 6. MCP Integration — `mcp/`

**路径：** `backend/packages/harness/deerflow/mcp/manager.py`

- 多 server MCP 客户端
- 支持 stdio、SSE、HTTP 三种 transport
- 自动 reload on config file change（mtime 缓存失效）
- OAuth token flow 支持 (`client_credentials`、`refresh_token`)

**复用可行性：中**。SwarmMind 目前没有 MCP 支持，如有需要可参考。

---

## 三、无法复用的部分

| 组件 | 原因 |
|------|------|
| **Frontend** | Next.js + Radix UI，SwarmMind 是 shadcn/ui + Vite |
| **LangGraph Agent** | 深度耦合 LangGraph（checkpointers、streaming、middleware chain），引入后难以剥离 |
| **Sandbox 系统** | 需要 Docker/Kubernetes + `agent-sandbox`，SwarmMind 没有这个依赖 |
| **Gateway API** | FastAPI REST API（models、MCP、skills、uploads、artifacts），SwarmMind 已有自己的 supervisor API |
| **IM Channels** | Telegram/Slack/Feishu WebSocket，SwarmMind 不需要 |
| **config.yaml 配置系统** | 深度耦合的配置体系（models、tools、sandbox、skills 分别配置），与 SwarmMind 的 `.env` 方案不同 |
| **Middleware Chain** | ThreadDataMiddleware、UploadsMiddleware、SandboxMiddleware、TitleMiddleware、TodoListMiddleware 等，耦合 LangGraph |

---

## 四、依赖风险

`deerflow-harness` 核心依赖：

```
langgraph>=1.0.6          # 大型框架，深度耦合
kubernetes>=30.0.0         # Sandbox 用
agent-sandbox>=0.0.19      # 沙盒执行
langchain-mcp-adapters>=0.1.0  # MCP 集成
tavily-python>=0.7.17     # 搜索
firecrawl-py>=1.15.0      # 爬虫
tiktoken>=0.8.0           # token 计数
langgraph-checkpoint-sqlite>=3.0.3  # 状态持久化
Python>=3.12               # 版本要求
```

**关键风险：**
- 引入 `deerflow-harness` 会带入 `langgraph` 依赖链，这是个大型框架
- 如果 SwarmMind 要保持轻量，不建议引入完整 harness 包

---

## 五、建议的复用方式

### 方案 A：直接 import `DeerFlowClient`（推荐）⭐

最干净的复用方式，只需 `deerflow-harness` 包：

```bash
cd /tmp/deer-flow/backend && uv sync
```

```python
from deerflow.client import DeerFlowClient

# 作为 SwarmMind 的执行引擎
client = DeerFlowClient(config_path="/path/to/deer-flow/config.yaml")

# SwarmMind 的 agent 创建/proposal 执行都走 DeerFlow
result = client.chat(goal_prompt, thread_id=thread_id)
```

**优点：** 无需启动 DeerFlow server 进程，纯 Python import
**缺点：** 需要 DeerFlow 的 config.yaml 和 skills 目录

### 方案 B：参考部分实现（低风险）

- 参考 `create_chat_model` 的 thinking/reasoning 配置 → 吸收到 `swarmmind/llm.py`
- 参考 Skills 格式 → 未来需要可插拔 skill 扩展时借用
- 参考 memory injection 策略 → 优化 `LayeredMemory`

### 方案 C：不推荐的方式

引入完整 `deerflow-harness` 作为正式 dependency。LangGraph 耦合太深，会改变 SwarmMind 架构，增加复杂度。

---

## 六、待验证事项

- [ ] `DeerFlowClient` 实际 import 是否顺畅（Python 3.12+ 环境）
- [ ] DeerFlow 的 config.yaml 是否可以被 SwarmMind 的 `.env` 方案替代
- [ ] DeerFlow 和 SwarmMind 的 agent 设计理念是否兼容（DeerFlow 是 harness/编排，SwarmMind 是协作式团队 OS）
