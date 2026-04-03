# SwarmMind UI Docs

> 日期：2026-04-03
> 用途：维护 `SwarmMind/ui/` 的页面骨架、全局交互规则和关键流程

## 1. 文档边界

UI 文档现在分成两层：

- [`DESIGN.md`](../../DESIGN.md)：唯一视觉与设计系统母稿
- `docs/ui/*`：页面骨架、导航、流程和线框说明

这次收敛后，`docs/ui` 不再承载独立视觉语言母稿。
颜色、字体、密度、圆角、阴影、动效边界、Chat/Project 气质差异，统一收口到 `DESIGN.md`。

## 2. 阅读顺序

1. [`DESIGN.md`](../../DESIGN.md)
2. `01-navigation-and-principles.md`
3. `02-page-map-and-flows.md`
4. `10-workbench-and-chat.md`
5. `20-skill-center.md`
6. `30-projects-and-project-space.md`
7. `40-approval-center.md`
8. `60-knowledge-library-schedules.md`

## 3. 每份文档负责什么

- `01-navigation-and-principles.md`
  - 全局导航、骨架、跨页规则、桌面端视口原则
- `02-page-map-and-flows.md`
  - 页面全集与关键主流程
- `10-workbench-and-chat.md`
  - 工作台、轻量 ChatSession、最近记录
- `20-skill-center.md`
  - 技能治理入口
- `30-projects-and-project-space.md`
  - 项目列表、项目空间与固定子页
- `40-approval-center.md`
  - 审批中心与相关抽屉
- `60-knowledge-library-schedules.md`
  - 资源库、知识库、定时任务、设置

## 4. 页面文档写法

页面文档默认保留这些部分：

- 页面卡片
- 信息结构
- 桌面端线框
- 关键交互
- 状态设计
- 平台范围约束

不再重复写这些内容：

- 全局视觉语言
- 字体和颜色总规范
- 阴影/圆角/动效边界
- 与其它文档重复的全局设计结论

## 5. 维护规则

- 跨页面视觉规则改 `DESIGN.md`
- 跨页面结构或导航规则改 `01` / `02`
- 单页面信息结构和交互改对应页面文档
- 若某条 UI 规则影响运行时语义，先改 `docs/architecture.md`，再回写到 UI 文档

## 6. 设计定位

SwarmMind 的 UI 不是“聊天壳 + 几个 tab”。
它是三层清晰控制面：

- 会话层：探索与发起
- 项目层：执行与协作
- 治理层：审批、技能、资产与权限化聚合
