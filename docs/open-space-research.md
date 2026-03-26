# OpenSpace 调研报告

> 调研时间：2026-03-26
> 仓库：https://github.com/HKUDS/OpenSpace
> 本地路径：~/workspace/OpenSpace

## 一、项目概述

**OpenSpace** 是港大 HUKS 团队开源的 AI Agent 自进化引擎，核心理念是让 Agent 通过技能（Skill）实现自我优化和群体共享。

```
"OpenSpace: Make Your Agents: Smarter, Low-Cost, Self-Evolving"
```

**核心技术指标：**

- **46% 更少 tokens** — 技能复用避免重复推理
- **4.2× 收入增长** — GDPVal 真实经济基准测试
- **165 个技能** — 从 50 个真实任务中自动演化而来
- **$11K 收益** — 6 小时内完成 50 个专业任务的实际经济价值

**技术栈：** Python 3.12+、MCP（Model Context Protocol）、SQLite

---

## 二、架构概览

### 2.1 核心定位对比

| | SwarmMind | OpenSpace |
|---|---|---|
| **核心抽象** | 共享上下文（KV Store）+ Context Broker 路由 | 自进化技能（Self-Evolving Skills） |
| **协调机制** | 目标分发到专精 Agent（关键词路由） | 技能跨 Agent 共享，集体进化 |
| **学习方式** | 策略表（Phase 1：关键词路由） | 执行后自动修复、自动改进、自动捕获 |
| **知识共享** | 共享内存（last-write-wins） | 云端技能社区 + lineage 追踪 |
| **技能生命周期** | 静态技能，无演化 | 动态演化：FIX / DERIVED / CAPTURED + 版本 DAG |
| **Token 效率** | Phase 1 暂无 | 46% 降低（技能复用） |
| **架构风格** | Context Broker → Agents → SharedMemory | SkillEngine（registry→analyzer→evolver）→ Cloud |

### 2.2 SwarmMind 架构

```
Human Supervisor → Context Broker → [Finance Agent, Code Review Agent, ...]
                           ↓
                    SharedContext (SQLite KV)
```

目标通过关键词路由到专精 Agent。技能固定，无演化能力。

### 2.3 OpenSpace 架构

```
Agent → Skill Registry（发现）→ Grounding Agent（执行）
                ↓                                    ↓
         Skill Store (SQLite) ← Execution Analyzer ← Recording
                ↓
         Skill Evolver ← 三大触发器：执行分析 / 工具降级 / 指标监控
                ↓
         Cloud Skill Community ← upload_skill / download_skill
```

---

## 三、核心组件详解

### 3.1 自进化引擎（Skill Engine）

#### 三种演化类型

| 类型 | 描述 | 亲子关系 |
|------|------|---------|
| **FIX** | 原地修复损坏/过时指令 | 1 个父版本 |
| **DERIVED** | 创建增强或专业化版本 | 1+ 个父版本 |
| **CAPTURED** | 从成功案例中提取新模式 | 无父版本（全新） |

#### 三大独立触发器

1. **Post-Execution Analysis（执行后分析）**
   - 每次任务完成后运行 `ExecutionAnalyzer`
   - 分析完整录制记录，建议进化方向

2. **Tool Degradation（工具降级）**
   - 当工具成功率下降时触发
   - `ToolQualityManager` 找到所有依赖技能并批量演化

3. **Metric Monitor（指标监控）**
   - 定期扫描技能健康状态
   - 追踪 `applied_rate`、`completion_rate`、`fallback_rate`

#### 质量指标（`types.py`）

```python
@dataclass
class SkillRecord:
    total_selections: int   # LLM 选择次数
    total_applied: int      # Agent 实际应用次数
    total_completions: int  # 技能应用后任务完成次数
    total_fallbacks: int    # 技能未应用且任务失败次数

    @property
    def applied_rate(self):      # total_applied / total_selections
    @property
    def completion_rate(self):   # total_completions / total_applied
    @property
    def effective_rate(self):     # total_completions / total_selections
    @property
    def fallback_rate(self):     # total_fallbacks / total_selections
```

### 3.2 云端技能社区（Cloud Skill Community）

HTTP 客户端访问 `open-space.cloud`，实现跨 Agent 技能共享：

- **`cloud/client.py`** — 技能上传/下载、工件暂存、元数据搜索
- **`cloud/search.py`** — 混合搜索（BM25 + embedding）
- **`cloud/embedding.py`** — 用于语义搜索的 embedding 生成

**可见性控制：** `PRIVATE`（仅创建者）/ `PUBLIC`（对所有 Agent 可见）

### 3.3 技能注册表（Skill Registry）

**选择管线（三阶段）：**

1. **BM25 粗排** — 快速词法过滤（取 top_k × 3 候选）
2. **Embedding 重排** — 对 BM25 候选做语义相似度
3. **LLM 最终选择** — 结合质量指标做决策

### 3.4 MCP 集成

通过 `mcp_server.py` 暴露 4 个 MCP Tools：

| Tool | 功能 |
|------|------|
| `execute_task` | 委托任务（自动注册技能、自动搜索、自动进化） |
| `search_skills` | 独立搜索本地和云端技能 |
| `fix_skill` | 手动修复损坏的技能（仅 FIX） |
| `upload_skill` | 将本地技能上传到云端社区 |

---

## 四、代码结构

```
openspace/
├── tool_layer.py              # OpenSpace 主类
├── mcp_server.py              # MCP Server（4 tools）
├── __main__.py                # CLI 入口
├── dashboard_server.py        # Web dashboard API
│
├── agents/                    # Agent 系统
│   ├── base.py               # BaseAgent 抽象类
│   └── grounding_agent.py    # GroundingAgent（执行引擎）
│
├── grounding/                 # 统一后端系统
│   ├── core/
│   │   ├── grounding_client.py
│   │   ├── quality/          # 工具质量追踪
│   │   ├── security/         # 沙箱策略
│   │   └── tool/             # 工具抽象
│   └── backends/
│       ├── shell/            # Shell 执行
│       ├── gui/             # Anthropic Computer Use
│       ├── mcp/             # MCP 客户端（stdio、HTTP、WS）
│       └── web/             # Web 搜索/浏览
│
├── skill_engine/             # 自进化技能系统
│   ├── registry.py          # 发现、选择、注入
│   ├── analyzer.py          # 执行后分析
│   ├── evolver.py           # FIX/DERIVED/CAPTURED
│   ├── patch.py             # 多文件 patch 应用
│   ├── store.py             # SQLite 持久化
│   ├── skill_ranker.py     # BM25 + embedding 混合排序
│   └── types.py             # 数据模型
│
├── cloud/                    # 云端技能社区
│   ├── client.py            # HTTP 客户端
│   ├── search.py            # 搜索引擎
│   └── cli/                 # download/upload CLI
│
├── host_skills/              # Agent 集成技能
│   ├── delegate-task/       # 委托任务技能
│   └── skill-discovery/     # 技能发现技能
│
├── prompts/                  # LLM prompt 模板
├── llm/                      # LiteLLM 封装
├── config/                   # 分层配置
├── recording/                # 执行录制
└── skills/                   # 内置技能（最低优先级）
```

---

## 五、技能格式

技能遵循官方 `SKILL.md` 格式：

```
skill-directory/
├── SKILL.md          # YAML frontmatter（name、description）+ markdown 正文
├── .skill_id         # 持久化唯一标识符（自动生成）
└── [辅助文件]        # 可选脚本、配置、示例
```

**示例（`delegate-task/SKILL.md`）：**

```markdown
---
name: delegate-task
description: Delegate tasks to OpenSpace — full-stack autonomous worker...
---

# Delegate Tasks to OpenSpace

OpenSpace is connected as an MCP server. You have 4 tools available:
`execute_task`, `search_skills`, `fix_skill`, `upload_skill`.

## When to use
- **You lack the capability** — task requires tools beyond what you access
- **You tried and failed** — OpenSpace may have a tested skill for it
...
```

---

## 六、GDPVal 经济基准测试

**数据集：** GDPVal — 220 个真实专业任务，44 个职业

**协议：** ClawWork 评估协议，LLM-based 评分

### 核心结果

| 指标 | 数值 |
|------|------|
| **收入倍数** | 4.2× vs ClawWork baseline |
| **价值捕获率** | 72.8%（$11,484 / $15,764 最大值） |
| **平均质量** | 70.8%（+30pp vs 最佳 ClawWork 40.8%） |
| **Token 降低（P2 vs P1）** | 45.9% |

### 分类表现

| 类别 | 收入 Δ | Token Δ |
|------|--------|---------|
| Documents & Correspondence | +3.3pp | −56% |
| Compliance & Form | +18.5pp | −51% |
| Media Production | +5.8pp | −46% |
| Engineering | +8.7pp | −43% |
| Spreadsheets | +7.3pp | −37% |
| Strategy & Analysis | +1.0pp | −32% |

### 技能分类（165 个演化技能）

| 目的 | 数量 | 示例 |
|------|------|------|
| File Format I/O | 44 | PDF extraction fallbacks, DOCX parsing |
| Execution Recovery | 29 | Sandbox fails → shell → heredoc fallback |
| Document Generation | 26 | End-to-end doc pipeline（13 个派生版本） |
| Quality Assurance | 23 | Post-write verification |
| Task Orchestration | 17 | Multi-file tracking, ZIP packaging |

---

## 七、设计模式分析

### 7.1 技能捕获成功工作流

技能从实际执行录制中提取。任务成功后：

1. `ExecutionAnalyzer` 审查对话和工具调用
2. LLM 识别成功模式
3. 如果新颖/可复用，创建 `CAPTURED` 技能

### 7.2 进化学习循环

```
任务执行 → 录制 → 分析 → 进化建议
                              ↓
                      ┌──────┴──────┐
                      ↓             ↓
                   FIX          DERIVED
                      ↓             ↓
                 更新的技能    新技能目录
                      ↓             ↓
                 共存与技能库中
```

**防循环机制：**

- **触发器 2（工具降级）**：状态驱动 — 追踪哪些技能已针对某工具处理过，工具恢复时清除
- **触发器 3（指标监控）**：数据驱动 — 新演化的技能需达到 `min_selections=5` 才重新评估

### 7.3 群体智能共享

Agent 进化改进后：
1. `upload_skill` 推送到 `open-space.cloud`
2. 其他 Agent 通过 `search_skills` 发现
3. `auto_import` 下载热门云端技能到本地

---

## 八、SwarmMind 可借鉴之处

### 8.1 技能系统（高优先级）

OpenSpace 的 SKILL.md 格式是标准化的技能规范，SwarmMind 的 Agent 目前缺乏可插拔技能机制。

**可复用设计：**
- 技能目录扫描 + `.skill_id` 自动生成
- 三阶段选择管线（BM25 → embedding → LLM）
- 技能元数据格式（`applied_rate`、`completion_rate` 等指标）

**参考路径：** `openspace/skill_engine/registry.py`、`openspace/skills/README.md`

### 8.2 自进化机制（中优先级）

三大触发器设计值得参考：
- **Post-Execution Analysis**：每次任务后分析录制，提取可复用模式
- **Tool Degradation**：工具降级时批量修复相关技能
- **Metric Monitor**：指标驱动的新技能再评估

**参考路径：** `openspace/skill_engine/analyzer.py`、`openspace/skill_engine/evolver.py`

### 8.3 质量追踪（中优先级）

`SkillRecord` 的量化指标体系可以借鉴：
- `applied_rate`：选择后实际应用率
- `completion_rate`：应用后任务完成率
- `effective_rate`：总体有效率
- `fallback_rate`：回退率

**参考路径：** `openspace/skill_engine/types.py`

### 8.4 云端技能社区（低优先级，当前 Phase 1 不需要）

分布式技能共享是 OpenSpace 的差异化特性，但 SwarmMind Phase 1 是本地单团队场景，暂不需要。

---

## 九、架构对比与融合思考

### 9.1 互补性分析

| 方面 | SwarmMind | OpenSpace |
|------|-----------|-----------|
| **优势** | 团队协作、目标路由、Supervisor UI | 技能演化、Token 效率、群体智能 |
| **劣势** | 无技能演化、Phase 1 简单路由 | 无团队协作机制 |
| **可融合点** | Context Broker 路由 → 路由到有 OpenSpace 技能演化的 Agent | OpenSpace 技能可作为 SwarmMind Agent 的底层能力 |

### 9.2 潜在融合路径

**方向 A：OpenSpace 作为 SwarmMind 的执行引擎**

```
Human Supervisor → Context Broker → OpenSpace Agent（带技能演化）
                                    ↓
                            Skill Engine（自进化）
                            Cloud Skill Community
```

- Context Broker 负责任务路由和分发
- OpenSpace Agent 作为执行引擎，提供自进化能力
- 可以利用 OpenSpace 的技能复用和 Token 优化

**方向 B：吸收技能选择管线**

保持 SwarmMind 的多 Agent 协作架构，吸收 OpenSpace 的三阶段技能选择：

1. BM25 粗排（快速过滤）
2. Embedding 重排（语义相似度）
3. LLM 最终选择（结合质量指标）

**方向 C：自进化机制集成**

在 SwarmMind 的 Agent 中引入执行后分析：
- 任务完成后分析对话录制
- 提取成功的策略模式
- 存入共享上下文供后续使用

---

## 十、总结

OpenSpace 是一个**技能中心化、进化驱动**的系统。其核心创新在于：

1. **每任务都是学习机会**：成功（CAPTURED）和失败（FIX）都驱动技能进化
2. **群体智能网络效应**：一个 Agent 学到，所有 Agent 受益
3. **Token 效率的量化验证**：GDPVal 基准证明 46% token 降低 + 4.2× 收入提升

SwarmMind 的核心优势在于**团队协作式 Agent 架构**和**人类监督机制**。两者可以在执行层（OpenSpace 技能进化）和协调层（SwarmMind Context Broker）形成互补。

**SwarmMind 可以借鉴优先级：**
1. ⭐ 高：SKILL.md 标准化技能格式 + 技能发现/选择管线
2. ⭐ 高：自进化触发器设计（执行后分析、工具降级、指标监控）
3. 🟡 中：质量指标量化体系（applied_rate、completion_rate 等）
4. 🟡 中：技能 lineage 追踪（DAG 版本管理）
5. 🔴 低：云端技能社区（Phase 1 本地场景暂不需要）
