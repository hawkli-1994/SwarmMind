# TeamInterfaceAgent ADR

> 状态：Accepted
> 日期：2026-03-27
> 关联文档：`docs/architecture.md`

## 1. 目标

定义 `TeamInterfaceAgent` 的 intake、routing 和 `thread_policy=reuse` 判定规则，使多成员协作在同一 `Project` 下仍保持：

- 上下文不混乱
- 审计可追踪
- 权限不泄漏
- 吞吐不被单入口完全串行化

## 2. 背景

在 `Project` 内，同一个 `AgentTeam` 模板会被实例化为 `ProjectTeamInstance`。
如果多个成员直接把请求打到同一个 Team 内工作 thread，会出现以下问题：

- 多个 run 同时写入同一 thread，导致上下文交织。
- 不同成员的工作目标混入同一会话，thread 失去工作流边界。
- 取消、重试、审批和审计难以归因到真实发起人。
- 不同权限成员复用同一 thread 时，容易造成上下文越权暴露。

因此在多成员协作场景中，需要引入一个项目内入口治理角色。

## 3. 决策

在需要多人共享协作入口的 `ProjectTeamInstance` 下，启用 `TeamInterfaceAgent` 作为统一入口。

它不垄断执行，只负责：

- 接收成员请求
- 校验 `RBAC`
- 归一化目标和上下文
- 识别工作流归属
- 判定是否复用 thread
- 将请求分发给具体 `AgentRuntimeInstance`

真正执行仍由被分配的 `AgentRuntimeInstance` 完成。

## 4. 核心模型

### 4.1 TeamInterfaceAgent

```text
TeamInterfaceAgent
  - interface_agent_id
  - project_id
  - project_team_instance_id
  - intake_policy
  - routing_policy
  - thread_reuse_policy
  - escalation_policy
```

### 4.2 Workstream

`TeamInterfaceAgent` 必须把成员请求先归类到显式工作流，而不是直接按原始文本决定是否复用 thread。

```text
Workstream
  - workstream_key
  - project_id
  - project_team_instance_id
  - topic
  - scope_summary
  - visibility_tier
  - active_thread_id
  - status
```

说明：

- `workstream_key` 表示“同一条持续推进的工作流”。
- 一个 `Project` 可以同时存在多个 `Workstream`。
- thread reuse 先判定是否属于同一 `Workstream`，再判定是否可复用其 thread。

### 4.3 InterfaceDecision

每次入口判定都应落成结构化记录。

```text
InterfaceDecision
  - decision_id
  - project_id
  - project_team_instance_id
  - actor_id
  - interface_agent_id
  - request_summary
  - workstream_key
  - decision_type      (reuse_thread | new_thread | dispatch_other_agent | escalate)
  - target_thread_id
  - target_agent_instance_id
  - reason_codes
  - decided_at
```

## 5. Intake 规则

`TeamInterfaceAgent` 在接到请求后，按如下顺序处理：

1. 校验 `RBAC`
2. 规范化请求文本
3. 提取目标、约束、涉及 artifact、涉及范围
4. 判断是否命中已有 `Workstream`
5. 给出 routing 与 thread reuse 决策

### 5.1 RBAC 校验

最低校验项：

- 没有 `project.view` 不允许读取项目上下文
- 没有 `project.run` 不允许发起执行
- 命中审批路径但没有 `project.approve` 时，只能提交待审 run，不能直接批准
- 没有 `artifact.read` 的成员，不得把受限 artifact 所在 thread 复用给该成员

### 5.2 请求归一化

归一化至少要产出以下字段：

```text
NormalizedRequest
  - actor_id
  - project_id
  - project_team_instance_id
  - intent_summary
  - requested_scope
  - referenced_artifact_refs
  - preferred_role
  - urgency
```

目标：

- 去掉口语化冗余
- 提取约束条件
- 识别是否是已有任务的连续推进
- 识别是否触发新的工作流

### 5.3 去重与合并

在短时间窗口内，如果两个请求满足以下条件，可被合并为同一个入口决策：

- 同一 `actor_id`
- 同一 `project_team_instance_id`
- 同一 `workstream_key`
- 目标语义高度相似

但不同成员请求默认不自动合并，只允许归入同一 `Workstream` 后继续独立审计。

## 6. Routing 规则

### 6.1 目标 Agent 选择

`TeamInterfaceAgent` 选择目标 `AgentRuntimeInstance` 时，至少考虑：

- `preferred_role` 是否存在
- 当前 `Workstream` 的历史归属
- 当前可用的 `allowed_profiles`
- 目标 agent 是否已有相关 thread 上下文
- 当前实例是否有活跃写入 run

默认策略：

- 同一 `Workstream` 连续推进时，优先复用同一 `AgentRuntimeInstance`
- 工作主题明显切换时，可路由到新的 `AgentRuntimeInstance`
- 若请求本质是协调、拆解、分派，则优先落到接口人或协调角色，而不是直接落到专业角色

### 6.2 入口人不是执行瓶颈

`TeamInterfaceAgent` 只治理入口，不应成为所有任务的串行执行者。

因此：

- intake 决策可以集中
- 执行可以分发
- 不同 `Workstream` 可以并行运行
- 同一 `Workstream` 下的 thread 写入必须串行

## 7. Thread Reuse 判定规则

只有当以下条件同时满足时，才允许 `reuse_thread`：

1. 同一 `project_id`
2. 同一 `project_team_instance_id`
3. 同一 `AgentRuntimeInstance`
4. 命中同一 `workstream_key`
5. actor 的权限等级不低于该 thread 已暴露的可见级别
6. 目标 thread 当前没有活跃写入 run
7. 本次运行 profile 与现有 thread 的语义兼容
8. thread 未超过策略定义的陈旧窗口

只要有任一条件不满足，默认创建新 thread。

### 7.1 语义兼容

以下情况视为不兼容，应新建 thread：

- 从“研究/分析”切到“执行/交付”
- 从低风险 profile 切到高风险 profile
- 从普通问答切到 `plan_mode + subagent`
- 请求目标从一个模块切换到另一个明显不同的模块
- 需要引入新的受限 artifact，而当前 thread 不具备该可见范围

### 7.2 权限兼容

thread reuse 必须满足最小权限约束：

- 低权限 actor 不得复用高权限 thread
- 访问范围更窄的 actor 可以触发新 thread，而不是降级复用旧 thread
- thread 的可见级别一旦提升，不应再向低权限成员开放复用

### 7.3 并发兼容

同一 thread 在任一时刻只允许一个活跃写入 run。

建议实现：

```text
ThreadLease
  - thread_id
  - run_id
  - lease_owner
  - acquired_at
  - expires_at
```

规则：

- 获取到 `ThreadLease` 后才允许向该 thread 发起写入型 run
- 未获取到 lease 时，不等待共享写入；默认新建 thread 或排队
- 只读诊断型请求不应默认进入共享工作 thread，除非策略明确允许

## 8. 审计规则

即使请求经过 `TeamInterfaceAgent`，审计也必须保留两层身份：

- 原始发起人 `actor_id`
- 入口治理者 `interface_agent_id`

每次 run 至少应记录：

- `actor_id`
- `interface_agent_id`
- `project_team_instance_id`
- `target_agent_instance_id`
- `workstream_key`
- `decision_type`
- `target_thread_id`
- `reason_codes`

这样才能回答：

- 谁提的请求
- 是谁决定复用还是新建 thread
- 最终由哪个运行实例执行

## 9. 失败、取消与重试

### 9.1 失败

- run 失败不回滚外部副作用
- 但 `InterfaceDecision` 与 `RunRecord` 必须保留
- thread 若因失败进入不可信状态，后续请求默认新建 thread

### 9.2 取消

- 取消作用于明确的 `run_id`
- 取消当前 run 不应自动取消同一 `Workstream` 下的其他 run
- 若 run 持有 `ThreadLease`，取消后必须释放 lease

### 9.3 重试

- 重试优先视为新的 `run_id`
- 是否沿用原 thread，仍需重新经过 reuse 判定
- 不能因为“这是重试”就跳过权限和兼容性检查

## 10. 非目标

本 ADR 不解决以下问题：

- Team 内部所有角色的细粒度调度算法
- DeerFlow 内部 memory 更新策略
- 跨 `Project` 的 thread 或 workstream 复用
- 自动判断所有请求语义是否完全一致的通用算法

## 11. 落地建议

第一阶段不追求复杂智能判定，可采用保守策略：

- 默认新 thread
- 只有显式命中同一 `Workstream` 且通过全部兼容性校验时才复用
- 复用失败时宁可多开 thread，也不要混用 thread

优先级顺序：

1. 先保证权限与审计正确
2. 再保证 thread 不混乱
3. 最后再优化复用率与吞吐
