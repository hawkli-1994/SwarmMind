# 企业级 CRM 项目用户故事

> 日期：2026-04-01
> 用途：用端到端用户故事校验 SwarmMind 简化后的 DeerFlow-first 架构是否闭环
> 关联文档：`docs/architecture.md`

## 1. 故事目标

本文通过一个企业员工发起 CRM 项目的完整故事，验证以下设计是否成立：

- `Project` 是否足以承担企业级协作、审计和权限边界
- `Agent Team` 是否可以作为稳定的用户心智模型存在
- DeerFlow `lead-agent + subagents` 是否足以在内部承载这个协作模型
- `WorkflowTemplate` 是否只需要作为控制面模板，而不是独立 runtime
- `MCP + Skill` 是否足以承接企业系统接入
- `RBAC`、审批、`RunStore`、`ArtifactStore`、`AuditLog` 是否能支撑真实企业治理

## 2. 角色

### 2.1 人类角色

- 企业员工用户：项目发起人，来自业务部门，负责提出需求、补充约束、反馈意见
- 企业高层 A：审批人之一，拥有更高权限，可批准高风险外部能力使用
- 技术负责人 B：项目协作者，负责评审方案与验收交付

### 2.2 AI 角色

- `软件开发 Agent Team`：用户在项目里看到的默认协作团队
- 产品专家
- 架构专家
- 交付规划专家
- 测试验证专家

这些角色首先是产品层可见概念。用户不需要知道它们在运行时如何映射到 DeerFlow。

## 3. 场景概述

一家企业准备建设新的 CRM 系统。业务部门希望三个月内交付 Web 版 MVP，覆盖客户管理、联系人管理、商机推进、销售跟进记录、基础权限和报表，并且必须接入公司现有 SSO。

企业员工用户登录 SwarmMind 后，可以先在轻量 `ChatSession` 中描述需求，也可以直接创建正式 `Project`。在这个故事里，用户先做一次探索对话，再把需求提升为项目。

## 4. 故事主线

### 4.1 从 ChatSession 提升为 Project

用户先在聊天中输入：

“我们想做一个销售团队先能用起来的 CRM MVP，三个月上线，先做 Web，必须接公司 SSO。第一期要支持客户、联系人、商机、跟进记录、基础权限和销售报表。”

DeerFlow 默认 agent 对需求做初步整理后，用户点击“提升为项目”。系统创建：

- `Project`
- 初始成员与角色绑定
- 项目级 thread / artifact 边界
- 空的 `TaskStore`、`RunStore`、`ArtifactStore`、`AuditLog`
- 一份由 ChatSession 语义压缩得到的项目初始文档

这一步验证：

- 轻量探索可以发生在 `ChatSession`
- 一旦要进入正式协作，必须落到 `Project`
- 项目文档资产比原始聊天 thread 更适合作为正式起点

### 4.2 选择 Agent Team

项目创建后，用户在项目设置中选择一个 `Agent Team`，例如“软件开发 Agent Team”。

这里用户看到的是 Team 配置模板，而不是某个已经在运行的项目内团队。
换句话说，Team 管理页更像在管理 Python 的 `class`。

在界面上，用户看到的是：

- 团队名称
- 团队成员角色
- 团队擅长的任务类型
- 团队当前绑定的项目

当用户把这个 Team 加入当前 `Project` 时，系统会创建一个 `ProjectAgentTeamInstance`。

在控制面上，这个实例默认对应：

- 默认 `LeadAgentProfile`
- 一个或多个 `WorkflowTemplate`
- 建议使用的 playbook / skill 组合
- 当前项目的 team instance 标识

这更像 Python 的实例化过程：

- Team 管理页里的 `AgentTeamTemplate` = `class`
- 项目里的 `ProjectAgentTeamInstance` = `instance`

用户不需要知道这些底层对象；对他来说，就是“这个项目现在接入了软件开发团队”。

这一步验证：

- `Agent Team` 可以作为用户稳定理解的协作入口
- Team 被加入项目后，确实存在一个 project-scoped 实例
- 这个实例是控制面实例，不需要变成一套独立 Team runtime
- workflow 模板和 runtime profile 可以隐藏在 Team 概念后面

### 4.3 Agent Team 接管正式项目启动

用户在项目工作台里发出第一条正式指令：

“请把这个 CRM MVP 项目拆成可执行方案，先明确范围、关键风险、里程碑和第一批任务。”

此时，从用户视角看，是 `软件开发 Agent Team` 开始协作：

- 产品专家负责梳理范围与优先级
- 架构专家负责识别系统边界与关键风险
- 交付规划专家负责拆里程碑和任务
- 测试专家负责提前补齐验收与风险检查

在内部，系统会用一个默认执行入口组织这些协作，并在需要时展开多 agent 分解。但这些细节不要求暴露给用户。

系统至少会完成：

- 读取项目初始文档
- 读取当前 `ProjectAgentTeamInstance`
- 注入当前 Team 对应的 workflow 资产
- 判断当前任务是否需要多步骤协作
- 组织多个专家角色的输出

最终系统返回的不是一段泛泛建议，而是一组结构化结果：

- MVP 范围说明
- 非目标列表
- 三个月里程碑草案
- 初版任务骨架
- 风险清单

这些结果被写入：

- `TaskStore` 中的任务元数据
- `ArtifactStore` 中的 PRD 草案、范围说明、架构草图
- `RunStore` 中的运行记录与事件索引
- `AuditLog` 中的重要决策摘要

这一步验证：

- 用户可以明确感知“团队在协作”
- SwarmMind 的价值在于把这种协作投影成项目控制面
- DeerFlow 协作能力足以在内部承载这一产品语义

### 4.4 项目看板与工作台出现

基于上一步产出，项目工作台开始出现结构化视图。当前最低公共视图是 `Kanban`，例如：

- `todo`
- `in_progress`
- `blocked`
- `done`

同时，项目概览页展示：

- 当前目标和范围
- 里程碑
- 主要风险
- 最近 runs
- 关键 artifacts

这里的看板并不是 DeerFlow 内部状态，而是 SwarmMind 控制面根据任务和运行结果生成的项目视图。

这一步验证：

- workflow 模板必须能映射成任务骨架和基础视图
- `Kanban` 是项目控制面的最小可视化单位

### 4.5 人类持续干预，而不是一次提需求后旁观

项目推进中，企业员工用户和技术负责人 B 可以持续补充要求，例如：

- “第一期先不要做复杂 BI 报表，只保留销售漏斗汇总。”
- “客户资料必须支持历史 CRM 批量导入。”
- “权限模型先按销售、经理、管理员三类角色实现。”

这些输入在界面上是“发给当前 Agent Team 的追加指导”。系统内部再由项目 Gateway 决定：

- 是否复用当前 thread
- 是否新开 thread 处理新主题
- 使用哪个 `LeadAgentProfile`
- 是否继续启用 `plan_mode` / `subagents`

这一步验证：

- 对用户来说，自己是在持续指导一个团队
- 对内部来说，多人协作入口治理可以由 `Project + Gateway + thread_policy` 完成
- 不需要额外设计 `TeamInterfaceAgent`

### 4.6 MCP + Skill 接入企业系统

推进到 SSO 和历史数据导入阶段时，项目需要接入企业现有系统：

- 身份认证系统
- 历史 CRM 数据源
- 内部知识库中的客户行业资料

SwarmMind 不为这些系统发明重型 connector 中台，而是采用：

- `MCP` 暴露工具能力
- `Skill` 告诉 DeerFlow 何时使用这些工具

例如：

- `sso-admin-mcp`
- `legacy-crm-mcp`
- `internal-kb-mcp`
- `crm-delivery` skill

项目层只需要决定：

- 该 `Project` 是否允许启用这些 MCP endpoints
- 当前 profile 是否允许调用相应 skills
- 哪些调用属于高风险

这一步验证：

- 企业系统接入的主路线可以保持为 `MCP + Skill`
- SwarmMind 只做项目级启用、审批和审计，不复制下游系统权限

### 4.7 高风险能力触发审批

当 `软件开发 Agent Team` 推进到需要读取内部知识库受限资料时，系统识别到这是高风险能力：

- 涉及受限数据源
- 可能需要更高权限 credential
- 会影响正式项目交付路径

因此本轮 run 被暂停，生成审批对象。审批信息至少包含：

- `project_id`
- `run_id`
- `selected_profile`
- 风险原因
- 计划调用的 MCP endpoint / tool namespace

企业员工用户可以看到：

- 当前阻塞点是什么
- 为什么需要审批
- 审批会影响哪些任务推进

但他没有批准权限，只能提交审批请求。

这一步验证：

- 审批对象是整轮高风险运行，而不是虚构的中间 proposal
- `RBAC` 决定谁能发起、谁能批准、谁只能查看

### 4.8 高层审批与恢复执行

企业高层 A 在审批中心看到这条请求后，可以审阅：

- 这是哪个项目发起的
- 为什么需要访问该系统
- 会调用哪些外部能力
- 不批准会阻塞哪些功能

若审批通过：

- 审批结果写入 `AuditLog`
- 该 run 恢复执行或允许重试
- 项目从 `blocked` 回到推进状态
- 用户继续看到团队协作恢复，而不需要理解底层 runtime 状态迁移

这一步验证：

- 审批上下文必须挂在 `Project` 与 `run_id` 上
- 审批人与执行人可以完全不是同一批人

### 4.9 高层驾驶舱

高层 A 还可以在驾驶舱中看到全局视图：

- 哪些项目在进行中
- 哪些项目被阻塞
- 哪些项目风险较高
- 最近有哪些高风险 run 等待审批
- 哪些项目交付接近完成

点进“新一代 CRM 平台建设”项目后，他能看到：

- 项目概览
- Kanban
- 关键 artifacts
- 最近运行记录
- 审批与风险记录

这一步验证：

- 驾驶舱是 `ProjectStore`、`RunStore`、`ArtifactStore`、`AuditLog` 的聚合视图
- 它不需要额外的“管理层专用执行引擎”

### 4.10 项目完成与归档

随着方案、开发、测试和验收逐步完成，项目中的任务和 artifacts 持续收敛。最终用户看到：

- 主要卡片进入 `done`
- MVP 范围完成交付
- 关键文档、方案、测试结果都已归档
- 审批链路完整可回放

项目结束后：

- 项目产物继续保留在 `Project`
- 有价值的 playbook 或知识总结可以沉淀到 `WorkflowAssetStore`
- DeerFlow memory 仍然是运行时记忆，不和控制面资产双写

这一步验证：

- `Project` 是正式执行与归档边界
- 工作流资产与项目产物必须分层

## 5. 这个故事验证了什么

### 5.1 被验证的设计

- `Project` 作为企业级协作边界是成立的
- `Agent Team` 可以保留为用户稳定心智模型
- Team 模板与项目内 Team 实例应明确分离
- 默认协作模型可以在内部建立在 DeerFlow `lead-agent + subagents` 之上
- `WorkflowTemplate` 只做控制面模板是足够的
- `MCP + Skill` 足以承接企业系统接入
- `RunStore`、`ArtifactStore`、`AuditLog` 是项目控制面的核心
- `RBAC` 和审批应围绕项目与 run 建模

### 5.2 暴露出的后续设计问题

这个故事也说明，后续还需要继续明确：

- `task_kind -> LeadAgentProfile` 的策略表如何设计
- `thread_policy=reuse` 的判定规则如何落成单独 ADR
- Kanban 与里程碑的数据模型如何保持简洁
- MCP 调用审计的最小 schema

## 6. 结论

如果 SwarmMind 要做的是企业级 AI work operating layer，而不是单次问答界面，那么这个故事说明简化后的方向更合理：

- 用 DeerFlow 作为唯一 runtime
- 对用户保留 `Agent Team` 作为主要协作概念
- 在控制面采用 `AgentTeamTemplate -> ProjectAgentTeamInstance` 的实例化模型
- 在内部用更薄的 DeerFlow 映射承载这个 Team 概念
- 用 `WorkflowTemplate` 提供控制面模板，而不是再发明 Team runtime
- 用 `Project`、`Run`、`Artifact`、`Audit` 形成真正可治理的控制面

如果这些点成立，用户看到的就是“项目在持续推进”；如果这些点缺失，用户看到的仍然只会是“一堆 agent 回复了很多话”。
