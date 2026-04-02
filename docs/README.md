# SwarmMind 文档总览

> 日期：2026-04-02
> 用途：定义当前文档体系的主入口，减少长期碎片化

## 1. 规范

- `docs/architecture.md` 是唯一主架构基线。
- UI 线框只保留在 `docs/ui/` 目录。
- 用户故事文档用于场景校验，不得反向覆盖主架构。
- 实现计划、调研草稿、过渡性架构稿不长期保留；一旦主要结论被吸收，应删除或并入正式文档。

## 2. 当前文档层次

### A. 主架构

- `docs/architecture.md`

用途：

- 定义术语表
- 定义控制面 / 执行面边界
- 定义 DeerFlow Runtime、RuntimeProfile、RuntimeInstance、Runtime Container
- 定义实施路线和非目标

### B. UI 线框

- `docs/ui/README.md`
- `docs/ui/00-v1-visual-language.md`
- `docs/ui/01-navigation-and-principles.md`
- `docs/ui/02-page-map-and-flows.md`
- `docs/ui/10-workbench-and-chat.md`
- `docs/ui/20-skill-center.md`
- `docs/ui/30-projects-and-project-space.md`
- `docs/ui/40-approval-center.md`
- `docs/ui/60-knowledge-library-schedules.md`

用途：

- 承接主架构到页面骨架
- 定义导航、布局、页面状态和交互规则

### C. 场景验证

- `docs/enterprise-crm-user-story.md`

用途：

- 保留一份规范场景文档，用端到端故事验证主架构和 UI 是否闭环
- 其他业务域的稳定结论优先并入 `docs/architecture.md`
- 不长期维护多份并行用户故事，避免再次引入旧术语和第二套对象模型

当前说明：

- 原 `marketing-campaign`、`hr-recruiting` 场景稿已删除。
- 它们留下的有效结论已收敛到 `docs/architecture.md` 的“跨业务场景边界”。
- 当前只保留 `enterprise-crm` 作为规范场景样本。

## 3. 清理规则

- 新增文档前，先判断能否写入现有正式文档。
- 若一个文档只服务某个阶段性实现或调研，应视为临时文档。
- 临时文档一旦被吸收，必须删除，不保留“长期 deprecated 文档”。
- 引用链必须指向当前正式文档，不应继续引用已删除的母稿或过渡稿。
- 研究类文档若已经偏离当前主路线，且未进入正式架构承诺，应删除而不是长期悬挂。
