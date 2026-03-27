# MCP + Skill 企业系统接入方案

> 日期：2026-03-27
> 用途：定义企业内部系统如何以 `MCP + Skill` 方式接入 SwarmMind
> 关联文档：`docs/architecture.md`、`docs/workflow-template-system.md`

## 1. 目标

SwarmMind 需要能接入真实企业已有系统，但前提是：

- 易于实施
- 易于定制
- 不依赖平台预知企业用了什么软件
- 不强行接管企业原生权限模型

因此，企业系统接入的主路线应当是：

`MCP + Skill`

其中：

- `MCP` 负责把企业系统能力暴露给 Agent
- `Skill` 负责告诉 Agent 何时、如何使用这些能力

SwarmMind 平台本身只补一层很薄的项目级启用、绑定和审计外壳。

## 2. 为什么选 MCP + Skill

如果平台面向不同企业销售，就无法假设客户统一使用某种系统。
现实情况往往是：

- 有的企业用 GitLab
- 有的企业用 GitHub Enterprise
- 有的企业用飞书审批
- 有的企业用 Jira
- 有的企业有自研知识库
- 有的企业有内部 HR、CRM、权限系统

这意味着平台不能先做一套重型、预定义很深的连接器中台。

相比之下，`MCP + Skill` 更现实：

- `MCP` 接口通用
- Skill 复用性高
- 开发门槛低
- 易于按企业定制
- 平台不必预知所有目标系统

## 3. 三层职责划分

### 3.1 MCP

`MCP` 的职责是：

- 暴露工具
- 描述工具输入输出
- 承担与企业系统的实际通讯

例如，一个 `gitlab-mcp` 可以暴露：

- `list_projects`
- `get_issue`
- `create_issue`
- `list_merge_requests`
- `create_merge_request`

### 3.2 Skill

`Skill` 的职责是：

- 告诉 Agent 什么时候用这些工具
- 如何组合这些工具完成某类任务
- 在什么前提下先查资料、再执行动作、再回写结果

例如：

- `gitlab-collaboration` skill
- `crm-requirement-analysis` skill
- `recruitment-approval-flow` skill

### 3.3 SwarmMind 平台侧薄治理

平台不做重型 connector 抽象，只做最小治理层：

- 某个 `Project` 是否允许使用某个 MCP
- 某个 Team / Workflow 默认绑定哪些 skill
- 调用了哪个 MCP tool
- 调用是否成功
- 哪些动作属于高风险，需要审批

## 4. 权限原则

最重要的原则是：

**SwarmMind 不接管企业系统原生权限。**

以 `GitLab` 为例：

- 连接器需要一个 `GitLab token`
- 这个 token 对哪些 group、repo、MR、issue 有权限，由 GitLab 自己决定
- SwarmMind 不再试图复制 GitLab 的细粒度权限模型

SwarmMind 只做外层治理：

- 这个 `Project` 能不能用 `gitlab-mcp`
- 这个 workflow 能不能调用 `gitlab` 相关 skill
- 某类动作是否需要额外审批
- 本次调用用了哪个 credential

所以权限分工应是：

- 下游系统负责资源级权限
- SwarmMind 负责项目级启用、审批和审计

## 5. 最小平台对象

虽然主路线是 `MCP + Skill`，但平台侧仍需要几个最小对象。

### 5.1 MCP Endpoint

表示某个企业已接入的 MCP 服务。

```text
McpEndpoint
  - endpoint_id
  - name
  - transport
  - connection_ref
  - auth_mode
  - tool_namespace
  - status
```

示例：

- `gitlab-prod`
- `internal-kb`
- `jira-core`

### 5.2 Skill Binding

表示哪些 skill 会被哪些 Agent / Team / Workflow / Project 默认启用。

```text
SkillBinding
  - binding_id
  - target_type       (agent | team | workflow_template | project)
  - target_ref
  - skill_ref
  - enabled_mcp_refs
```

说明：

- `target_type=agent` 适用于单个 Agent 的默认技能包
- `target_type=team` 适用于整个 `AgentTeam` 的默认技能包
- `target_type=workflow_template` 适用于流程模板推荐技能
- `target_type=project` 适用于项目级临时启用或覆盖

### 5.3 MCP Binding

表示哪些 MCP endpoint 会被哪些 Agent / Team / Project 允许使用。

```text
McpBinding
  - binding_id
  - target_type       (agent | team | project)
  - target_ref
  - endpoint_id
  - allowed_tool_namespaces
  - approval_policy_ref
  - status
```

### 5.4 Project MCP Allowlist

表示项目级别允许使用哪些 MCP 端点。

```text
ProjectMcpBinding
  - project_id
  - endpoint_id
  - allowed_tool_namespaces
  - approval_policy_ref
  - status
```

这层只做“能不能在这个项目里用”，不做底层系统的资源级授权。

### 5.5 SkillCenter

平台应提供一个面向用户的 `SkillCenter`，作为侧边栏中的独立入口。

`SkillCenter` 的职责：

- 浏览已安装的 `MCP` endpoint
- 浏览可用的 `Skill`
- 查看每个 skill 依赖哪些 MCP
- 把 skill 绑定到 `Agent` 或 `AgentTeam`
- 把 MCP 绑定到 `Agent`、`AgentTeam` 或 `Project`
- 查看绑定关系是否生效

推荐 UI 结构：

- 侧边栏入口：`技能中心`
- 一级标签：`MCP`、`Skills`、`Bindings`
- 详情页支持：
  - endpoint 状态
  - skill 描述
  - 绑定目标
  - 风险级别
  - 最近调用记录

设计原则：

- 用户应能在一个地方完成 `MCP` 和 `Skill` 管理
- 绑定动作不应散落在多个设置页里
- `SkillCenter` 是配置与治理入口，不是运行时聊天界面

## 6. 推荐接入方式

### 6.1 企业系统接入

推荐方式：

1. 企业提供某个系统的 MCP server
2. 在 SwarmMind 中注册为 `McpEndpoint`
3. 在 `SkillCenter` 中将相关 skill 绑定给 Agent、Team 或 Workflow
4. 在 `SkillCenter` 或 `Project` 中启用允许使用的 MCP

### 6.2 不强制 MCP-first 开发框架

如果企业已经有现成 MCP server，直接接入即可。
如果没有，也可以：

- 由企业自己写一个很薄的 MCP wrapper
- 或由平台提供参考实现，把 HTTP API 包装成 MCP tools

关键点是：

- 平台消费的是 MCP
- Skill 组合的是 MCP tools
- 企业接入方不需要理解整个平台内部架构

## 7. GitLab 示例

以 `GitLab` 为例，一个现实可落地的接入方式如下。

### 7.1 企业提供 GitLab MCP

企业部署一个 `gitlab-mcp`，内部持有：

- GitLab base URL
- GitLab token

它暴露例如：

- `gitlab.list_projects`
- `gitlab.get_issue`
- `gitlab.create_issue`
- `gitlab.list_merge_requests`
- `gitlab.create_merge_request`
- `gitlab.add_comment`

### 7.2 平台侧配置

SwarmMind 中配置：

- 一个 `McpEndpoint`: `gitlab-prod`
- 一个或多个 skill，例如 `gitlab-collaboration`
- 在 `SkillCenter` 中把 `gitlab-collaboration` 绑定给 `软件开发 Team`
- 某个 `Project` 启用 `gitlab-prod`

### 7.3 实际运行

当 `软件开发 Team` 在某个 `Project` 中推进任务时：

- Agent 根据 skill 判断何时查询 issue 或创建 MR
- 调用的是 `gitlab-mcp` 暴露的 tools
- GitLab token 是否有真实权限，由 GitLab 本身决定

SwarmMind 只负责：

- 这个项目是否启用了 `gitlab-prod`
- 这次 run 是否调用了相关 tool
- 这个动作是否属于高风险
- 是否需要额外审批

## 8. 审批模型

`MCP + Skill` 并不意味着所有调用都自动放行。

平台仍可对高风险操作加外层审批，例如：

- 写入类操作
- 批量修改
- 删除类操作
- 调用高权限 MCP endpoint

但审批对象不应是下游系统权限本身，而应是：

- 是否允许这次 run 使用某个高风险 tool
- 是否允许切换到更高权限的 credential / endpoint

也就是说：

- GitLab 仍决定 token 能干什么
- SwarmMind 决定这次项目流程要不要允许 Agent 发起这类调用

## 9. 与 Workflow 的关系

`WorkflowTemplate` 可以声明自己默认依赖哪些技能和外部能力。

例如：

```text
WorkflowTemplate
  - required_skill_refs
  - optional_skill_refs
  - recommended_mcp_namespaces
```

这意味着：

- `软件开发` 工作流模板可以推荐 `gitlab.*`
- `招聘` 工作流模板可以推荐 `hr.*`、`approval.*`
- `销售培训` 工作流模板可以推荐 `kb.*`、`docs.*`

但真正是否启用，仍由企业实际接入的 MCP 和项目配置决定。

## 10. 最小审计要求

每次 MCP tool 调用，平台至少应记录：

- `project_id`
- `run_id`
- `actor_id`
- `agent_instance_id`
- `endpoint_id`
- `tool_name`
- `status`
- `started_at`
- `finished_at`

如果失败，还应能看到：

- 是平台侧禁止
- 是审批未通过
- 还是下游系统因权限不足或接口错误返回失败

## 11. 对当前产品的建议

如果以最小可落地范围推进，建议：

1. 平台明确 `MCP + Skill` 是企业系统接入主路线
2. 先提供侧边栏 `SkillCenter`
3. 先支持 `Agent` / `Team` / `Project` 三级绑定
4. 先支持最小 MCP 调用审计
5. 先用 `GitLab` 和“内部知识库”做两个样板接入

## 12. 结论

企业系统接入不应先做成重型连接器平台。

当前最现实的路线是：

- 用 `MCP` 解决工具接入
- 用 `Skill` 解决使用套路
- 用很薄的平台外壳解决项目启用、审批和审计

这条路线足够通用，也更容易在真实企业环境里实施和定制。
