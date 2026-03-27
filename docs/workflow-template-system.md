# 工作流模板体系设计

> 日期：2026-03-27
> 用途：定义内置工作流、自定义工作流、隐藏式工作流设计 Agent 与最小可视化要求
> 关联文档：`docs/architecture.md`、`docs/enterprise-crm-user-story.md`

## 1. 目标

SwarmMind 不应只提供一个“通用 Agent Team 容器”，而应提供一套可复用的工作流模板体系：

- 平台内置一批高频工作流
- 用户可通过自然语言自定义工作流
- 自定义工作流由隐藏式设计 Agent 转换为规则与模板 schema
- 所有工作流都以 `Project` 为运行边界
- 所有工作流至少能投影出 `Kanban`

## 2. 两类工作流来源

### 2.1 平台内置工作流

SwarmMind 发布时内置一批标准工作流模板，例如：

- 软件开发
- 销售培训
- 自媒体运营
- 招聘

这些模板由平台维护，特点是：

- 结构稳定
- 默认角色与阶段清晰
- 适合直接给企业开箱即用
- 可作为用户自定义工作流的参考起点

### 2.2 用户自定义工作流

用户也可以直接描述自己的流程，例如：

- “帮我设计一个新品上市活动推进流程”
- “我们要做一个销售入职培训工作流”
- “我想把招聘从 JD 到 offer 的流程做成一个可协作项目模板”

用户不需要自己写 schema、状态机或规则文件。
他只需要用自然语言描述：

- 目标是什么
- 主要阶段有哪些
- 参与角色有哪些
- 哪些节点需要审批
- 哪些结果需要被看板追踪

剩下的模板抽象工作由系统内部 Agent 完成。

## 3. 隐藏式工作流设计 Agent

### 3.1 定位

系统中应存在一个对用户不可见的内部 Agent：

`WorkflowDesignerAgent`

它不是业务执行 Team 的成员，也不直接参与项目交付。
它的职责是把用户语言描述转成结构化工作流模板。

### 3.2 输入

它接收的输入可以来自：

- 用户新建自定义 Team 时的自然语言描述
- 用户对已有模板的修改要求
- 企业管理员对行业模板的定制请求

典型输入例如：

“我要一个招聘工作流，先做 JD 审核，再做渠道发布、简历筛选、面试安排、面试反馈、offer 审批和入职准备。需要 HR、用人经理和面试官参与。offer 发出前必须审批。”

### 3.3 输出

`WorkflowDesignerAgent` 的输出至少应包括：

- 工作流阶段定义
- 默认任务类型
- 默认角色清单
- 阶段转移规则
- 审批节点定义
- 最小可视化配置
- 模板 schema

它产出的不是最终项目数据，而是可复用模板。

## 4. 工作流模板的最小结构

最小 schema 可以定义为：

```text
WorkflowTemplate
  - workflow_template_id
  - name
  - source_type          (built_in | generated | customized)
  - objective
  - phase_definitions
  - role_definitions
  - task_blueprints
  - approval_checkpoints
  - visualization_config
  - version
  - status
```

关键字段说明：

- `source_type=built_in` 表示平台内置模板
- `source_type=generated` 表示由 `WorkflowDesignerAgent` 从自然语言生成
- `source_type=customized` 表示基于已有模板修改后的企业版本

## 5. 与 Team 的关系

`AgentTeam` 和 `WorkflowTemplate` 不是同一个东西，但应当关联：

- `AgentTeam` 决定“谁来协作”
- `WorkflowTemplate` 决定“如何推进”

因此，一个 Team 可以绑定一个默认工作流模板。
复杂场景下，也允许：

- 同一个 Team 支持多个工作流模板
- 同一个工作流模板被多个 Team 复用

对于“软件开发 Team”这种强领域模板，通常会表现为：

- 固定 Team 模板
- 固定默认工作流模板
- 用户在 `Project` 内再按需微调

## 6. Project 启动时如何落地

当用户在 `Project` 中选择某个 Team 后，系统应：

1. 确定对应的 `WorkflowTemplate`
2. 在 `Project` 内实例化为项目级工作流
3. 生成任务骨架与初始阶段
4. 生成最小可视化视图
5. 将入口接到 `TeamInterfaceAgent`

项目内运行的不是模板本身，而是：

- `ProjectTeamInstance`
- Project-scoped workflow instance
- 由此派生出的任务、审批与视图

## 7. 最小可视化要求

图表体系可以逐步演进，但当前必须有一个明确下限：

### 7.1 Kanban 是最低要求

每个工作流模板都必须能投影为 `Kanban`。

最少应支持：

- `todo`
- `in_progress`
- `blocked`
- `done`

如果模板需要，也可以有更细列，例如：

- `requirements`
- `design`
- `implementation`
- `review`
- `validation`

### 7.2 其他图表是可选增强

以下视图不是所有模板都必须有：

- 甘特图
- 时间线
- 风险热力图
- 依赖图
- 燃尽图

这些应由 `visualization_config` 和模板复杂度决定，而不是强制所有项目都显示。

## 8. 自然语言生成流程

用户创建自定义工作流时，推荐流程如下：

1. 用户用自然语言描述工作流
2. `WorkflowDesignerAgent` 进行结构化提炼
3. 生成模板草案
4. 用户确认或修订
5. 模板保存为企业可复用模板
6. 后续 `Project` 可直接选择该模板

用户看到的是：

- 一份清晰的阶段列表
- 一组默认角色
- 一张可用的看板结构
- 一些关键审批节点

用户不需要看到的是：

- 中间 prompt
- schema 归纳细节
- 内部规则转换过程

## 9. 生成约束

为了避免 `WorkflowDesignerAgent` 生成一套不可执行的空模板，必须加约束：

- 模板必须存在明确阶段
- 模板必须能映射成任务
- 模板必须能映射成 `Kanban`
- 模板必须指明哪些节点可能需要人工审批
- 模板必须能够绑定到至少一个 Team 角色
- 模板不能依赖 DeerFlow 内部 memory 才能成立

## 10. 版本化与修改

工作流模板必须版本化。

允许的演化方式：

- 平台升级内置模板
- 企业管理员复制并定制内置模板
- 用户基于已有模板追加阶段或审批点
- `WorkflowDesignerAgent` 重新生成新版本草案

但需要注意：

- 已运行的 `Project` 不应被模板新版本直接破坏
- 模板升级应作用于后续项目，或以显式迁移方式作用于当前项目

## 11. 这份设计验证了什么

这份设计明确了三件事：

1. `AgentTeam` 不等于工作流模板
2. 自定义工作流不要求用户自己写结构化配置
3. `Kanban` 是最小公共视图，其他图表都可以后续演进

## 12. 对当前产品的建议

如果当前要压缩范围，建议优先做：

1. 内置 `软件开发` 工作流模板
2. 内置 `招聘` 工作流模板
3. 自定义工作流的自然语言生成草案
4. `Kanban` 作为唯一必备项目视图

等这些稳定后，再逐步补：

- 甘特图
- 风险图
- 更复杂的模板编辑器
- 模板市场或共享机制
