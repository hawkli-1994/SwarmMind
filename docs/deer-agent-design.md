# GeneralAgent 设计方案

> ⚠️ **已废弃** — 本文档描述的设计已被 [架构文档](architecture.md) 中的 **AgentAdapter 架构**取代。
>
> DeerFlow 不再通过 `GeneralAgent` 直接耦合，而是通过 `DeerFlowAdapter`（Local Adapter）接入。
> 参见：[架构文档 - AgentAdapter 定义](architecture.md#四agent-interface-定义)

> 状态：✅ 已实现
> 实现文件：`swarmmind/agents/general_agent.py`
> 基于 DeerFlow（`bytedance/deer-flow`）

## 一、目标

将 DeerFlow 封装为 SwarmMind 的默认通用 Agent（`GeneralAgent`），用于处理**所有未匹配到专业 Agent 的任务**。

- SwarmMind 保持为**编排层**（routing、approval、context management）
- DeerFlow 作为**执行引擎**（tool execution、subagent orchestration、memory、checkpointing）
- 各司其职，不破坏现有架构

## 二、为什么需要 GeneralAgent

SwarmMind 原有 Agent（FinanceAgent、CodeReviewAgent）特点：
- 接收目标 → LLM 推理 → 生成 proposal → 人类审批 → 执行
- 适合**短程、结构化**任务

DeerFlow 擅长：
- 多步复杂推理（subagent decomposition）
- 工具执行（bash、web search、file I/O）
- 长程任务（checkpointing 持久化）
- Skills 系统（可插拔 prompt 片段）

**互补而非竞争。** GeneralAgent 是 SwarmMind agent 能力的**增强**，而非替代。

---

## 三、已实现的架构

```
Human Supervisor
       │
       ▼
┌──────────────────┐     ┌─────────────────────────────────────────┐
│   Supervisor UI  │     │          Context Broker                  │
│   (shadcn/ui)    │ ←── │  derive_situation_tag() → route_to_agent│
└──────────────────┘     └──────────┬──────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────────────┐
│   Finance   │          │   Code       │          │   GeneralAgent      │
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
                                              │
                                    ┌─────────▼─────────┐
                                    │   Shared Memory   │
                                    │  (LayeredMemory)  │
                                    └───────────────────┘
```

### 关键设计原则

1. **GeneralAgent 是 SwarmMind 的 fallback agent**，遵循相同接口（接收 goal → 生成 proposal → 执行）
2. **DeerFlow 是执行引擎**，DeerFlowClient 以 embedded 模式运行（无 server 进程）
3. **SwarmMind 保持控制**，GeneralAgent 执行结果写入 LayeredMemory，人类可通过 UI 监控
4. **隔离性好**，DeerFlow 的 LangGraph 依赖不会扩散到整个 SwarmMind

### 实现细节

| 细节 | 值 |
|------|-----|
| `domain_tags` | `[]`（GeneralAgent 不读取特定域的内存） |
| 写入内存的 tags | `["general"]`（goal/tag 结果）、`["general", "tools"]`（工具调用摘要） |
| 更新 proposal 的 confidence | `0.8`（硬编码） |
| 继承自 BaseAgent | `_resolve_write_scope()`、`memory`、`_create_rejected_proposal()` |

---

## 四、路由逻辑

```
用户消息 → derive_situation_tag() → route_to_agent()
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            Finance Agent         Code Review Agent         GeneralAgent
            (关键词匹配)           (关键词匹配)           (fallback: unknown→general)
```

### derive_situation_tag() 关键词映射

| situation_tag | 触发关键词示例 |
|--------------|--------------|
| `finance` | finance, financial, revenue, expense, profit, quarterly, Q1-Q4, fiscal, budget... |
| `code_review` | code, review, PR, pull request, git, python, bug, refactor... |
| `unknown` | （无匹配时默认）→ 映射到 `general` |

### 策略表种子数据

| situation_tag | agent_id | 说明 |
|--------------|---------|------|
| finance | finance | |
| finance_qa | finance | |
| quarterly_report | finance | |
| revenue_analysis | finance | |
| code_review | code_review | |
| python_review | code_review | |
| pr_review | code_review | |
| **unknown** | **general** | fallback |

---

## 五、配置

### DeerFlow config.yaml

```yaml
# DeerFlow 的标准配置，GeneralAgent 直接引用
# 模型和工具配置取决于实际部署环境，以下为示例
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

> **注意**：config.yaml 中的模型名称和 API Key 需要与实际 DeerFlow 部署环境匹配。DeepSeek、Claude 等只是示例。

### SwarmMind .env

```bash
# DeerFlow 配置路径（指向 DeerFlow 的 config.yaml）
DEER_FLOW_CONFIG_PATH=/path/to/deer-flow/config.yaml

# （已定义但当前代码未使用）
DEER_FLOW_SKILLS_PATH=/path/to/deer-flow/skills
```

> **注意**：`DEER_FLOW_SKILLS_PATH` 在 `config.py` 中已定义，但 `GeneralAgent` 当前实现中**未使用**。预留用于未来通过 DeerFlow Skills 系统注入 prompt 片段。

### GeneralAgent 初始化参数

```python
GeneralAgent(
    deer_flow_config_path: str | None = None,  # 优先用此参数，否则用 DEER_FLOW_CONFIG_PATH
    default_model: str | None = None,           # 覆盖 DeerFlow config.yaml 中的模型
    thinking_enabled: bool = True,              # 是否启用思考模式
)
```

---

## 六、DeerFlowClient 接口

GeneralAgent 使用 `DeerFlowClient` 的以下接口：

| 方法 | 用途 |
|------|------|
| `DeerFlowClient(config_path, model_name, thinking_enabled)` | 构造函数 |
| `client.stream(goal, thread_id)` | 流式执行目标，返回事件迭代器 |

### 事件类型处理

```python
# GeneralAgent 中处理的事件类型
"messages-tuple"  →  data["type"] == "ai"       → 提取最终文本
                   →  data["type"] == "tool"    → 记录工具调用
"end"             →  流式结束
```

---

## 七、复用策略

| DeerFlow 组件 | 复用方式 | 状态 |
|--------------|---------|------|
| `DeerFlowClient` | 直接 import，embedded 模式 | ✅ 可行 |
| Model factory (`create_chat_model`) | 参考 thinking/reasoning 配置 | ✅ 已在 LLMClient 参考 |
| Subagent 系统 | 通过 DeerFlowClient 间接使用 | ✅ 可行 |
| Tools (web search, bash, file I/O) | 通过 DeerFlow 沙盒执行 | ✅ 可行 |
| Skills system | 预留接口（`DEER_FLOW_SKILLS_PATH`），代码未使用 | ⚠️ 待实现 |
| Memory system | DeerFlow 内部使用，不影响 LayeredMemory | ✅ 隔离 |
| LangGraph Agent runtime | DeerFlow 内部隐藏 | ✅ 隔离 |
| Sandbox isolation | DeerFlow 内部 Docker/Kubernetes | ⚠️ 需要环境支持 |
| Gateway API | 不使用（用 SwarmMind supervisor） | ✅ 避免 |
| IM Channels | 不使用 | ✅ 避免 |

---

## 八、安装说明

```bash
# 1. DeerFlow 需要独立安装（不是 uv optional dependency）
#    参见 DeerFlow 官方仓库：https://github.com/bytedance/deer-flow
#    典型步骤（可能因版本而异）：
cd /path/to/deer-flow
pip install -e .

# 2. 在 SwarmMind .env 中配置路径
DEER_FLOW_CONFIG_PATH=/path/to/deer-flow/config.yaml

# 3. 确保 DeerFlow 的依赖（LangGraph 等）已安装
#    如果 DeerFlow 未安装，GeneralAgent 会抛出清晰的错误：
#    "DeerFlow is not installed. Install it with ..."

# 4. 验证导入（可选）
python -c "from deerflow.client import DeerFlowClient; print('DeerFlow OK')"
```

> ⚠️ **当前状态**：`pyproject.toml` 中**没有** `deerflow` 可选依赖。所有 DeerFlow 相关的导入都通过 `try/except ImportError` 捕获，实现优雅降级（DeerFlow 未安装时 GeneralAgent 报错，但不影响 SwarmMind 其他功能）。

---

## 九、风险与 Mitigation

### 风险 1：DeerFlow 依赖污染

LangGraph、kubernetes 等依赖会随 DeerFlow 引入。

**Mitigation：**
- DeerFlow 作为可选依赖，不在 core requirements 中
- GeneralAgent 封装所有 DeerFlow 调用，其他 SwarmMind 代码不直接 import DeerFlow
- DeerFlow 未安装时，GeneralAgent 抛出清晰的错误信息

### 风险 2：DeerFlow config.yaml 与 SwarmMind .env 并存

两组配置系统，增加运维复杂度。

**Mitigation：**
- DeerFlow config.yaml 路径通过 `DEER_FLOW_CONFIG_PATH` 环境变量配置
- SwarmMind 保持 .env 管理自己的配置
- 未来考虑将 DeerFlow 配置迁移到 SwarmMind 配置系统

### 风险 3：Sandbox 环境要求

生产环境需要 Docker/Kubernetes。

**Mitigation：**
- 开发环境用 `LocalSandboxProvider`
- 生产环境用 `AioSandboxProvider` + Docker
- 评估是否需要沙盒；如不需要（纯研究任务），可用 Local 模式

### 风险 4：`DEER_FLOW_SKILLS_PATH` 未实现

配置已定义但代码未使用。

**Mitigation：**
- 当前不影响功能，只是预留接口
- 如需使用，需在 GeneralAgent 中添加对 `DEER_FLOW_SKILLS_PATH` 的读取和应用逻辑
