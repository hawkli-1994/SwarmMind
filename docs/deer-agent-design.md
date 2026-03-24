# GeneralAgent 设计方案（已实现）

> 状态：✅ 已实现
> 实现文件：`swarmmind/agents/general_agent.py`
> 基于 DeerFlow v2.0 (`bytedance/deer-flow`)

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
│   (shadcn/ui)    │ ←── │  routes goals → agents                   │
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
                                    │                           │
                                    └───────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │   Shared Memory   │
                                    │  (LayeredMemory)  │
                                    └───────────────────┘
```

### 关键设计原则

1. **GeneralAgent 是 SwarmMind 的 fallback agent**，遵循相同接口（接收 goal → 生成 proposal → 执行）
2. **DeerFlow 是执行引擎**，DeerFlowClient 以 embeded 模式运行（无 server 进程）
3. **SwarmMind 保持控制**，GeneralAgent 执行结果写入 LayeredMemory，人类可通过 UI 监控
4. **隔离性好**，DeerFlow 的 LangGraph 依赖不会扩散到整个 SwarmMind

---

## 四、路由逻辑

```
用户消息 → derive_situation_tag() → route_to_agent()
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
            Finance Agent         Code Review Agent         GeneralAgent
            (关键词匹配)           (关键词匹配)           (fallback: 无匹配)
```

### 策略表种子数据

| situation_tag | agent_id |
|--------------|---------|
| finance | finance |
| finance_qa | finance |
| quarterly_report | finance |
| revenue_analysis | finance |
| code_review | code_review |
| python_review | code_review |
| pr_review | code_review |
| **unknown** | **general** |

---

## 五、配置

### DeerFlow config.yaml（DeerAgent 用）

```yaml
# DeerFlow 的标准配置，GeneralAgent 直接引用
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

## 六、复用策略

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

## 七、风险与 Mitigation

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

---

## 八、安装说明

```bash
# 1. 安装 DeerFlow（需要 Python>=3.12）
cd /path/to/deer-flow/backend/packages/harness
pip install -e .

# 2. 在 SwarmMind .env 中配置路径
DEER_FLOW_CONFIG_PATH=/path/to/deer-flow/backend/config.yaml
DEER_FLOW_SKILLS_PATH=/path/to/deer-flow/backend/data/skills
```
