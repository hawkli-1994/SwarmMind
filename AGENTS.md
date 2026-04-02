# SwarmMind — Agents Documentation

**AI agent team operating system. v0.9.0 — DeerFlow-first simplified architecture.**

> **Architecture baseline**: `docs/architecture.md` is the single source of truth.
> If code conflicts with architecture, code must be refactored.

## Terminology (Mandatory)

Using unqualified `Agent` in architecture discussions is prohibited. Always use qualified terms:

| Term | Meaning |
|------|---------|
| **Agent Team** | Product-level team collaboration entry visible to users |
| **AgentTeamTemplate** | Reusable team configuration template (control plane, not runtime) |
| **ProjectAgentTeamInstance** | A Team template instantiated within a specific Project |
| **Lead Agent** | DeerFlow Runtime's root execution agent |
| **Subagent** | DeerFlow Runtime's child agent, delegated by Lead Agent |
| **DeerFlow Runtime Instance** | A single independent DeerFlow execution unit with its own config boundary |
| **Runtime Container** | A DeerFlow Runtime Instance deployed in container form |
| **RuntimeProfile** | Versionable control-plane configuration for a DeerFlow Runtime |
| **RuntimeProvisioner** | Control-plane component that provisions and manages Runtime Instances |
| **thread** | DeerFlow's conversation state anchor (runtime context, not product object) |
| **Run** | Auditable, replayable control-plane execution record |
| **Task** | Control-plane task skeleton that can be routed and tracked |

**Compatibility notes for current code**:
- `GeneralAgent`, `FinanceAgent`, `CodeReviewAgent` → SwarmMind control-plane adapters, not DeerFlow Runtime Instances
- `DeerFlowClient` → Embedded DeerFlow client, not a Lead Agent or RuntimeProfile
- `lead-agent + subagents` → DeerFlow internal collaboration structure, not product-level Team templates

## Core Principles

### 1. Control-Execution Separation
- **Control Plane**: Broker, Router, Supervisor API/UI, Committer — routing, strategy, approval, audit
- **Execution Plane**: DeerFlow Runtime, MCP tools, HTTP tools — action execution
- Execution plane does not directly submit shared control-plane state

### 2. Project Is the Only Work Boundary
- `Project` is the sole formal workspace for tasks, data, approvals, artifacts, and audit
- Multi-user collaboration, workflow, and governance all happen within a Project
- `ChatSession` is a first-class lightweight entry (not a trial mode)
- ChatSession can be promoted to Project via semantic compression

### 3. DeerFlow Is the Only Execution Kernel
- All execution (ChatSession + Project) goes through DeerFlow Runtime
- No parallel native `LLMClient` execution path
- DeerFlow unavailability = explicit error + restart, not graceful degradation
- No multi-engine symmetric abstraction

### 4. User Concepts vs Runtime Mapping Separation
- Product-level `Agent Team` maps internally to `AgentTeamTemplate + ProjectAgentTeamInstance + LeadAgentProfile + RuntimeProfile`
- SwarmMind does not build its own Team runtime — uses DeerFlow native collaboration

### 5. DeerFlow Native Semantics First
- DeerFlow's stable capabilities (thread, chat/stream, artifact, upload, skill, plan_mode, subagent) are taken as-is
- Abstraction layers yield to DeerFlow when conflicts arise

### 6. Transport and Trust Modeling
- `local/remote` = communication method; `trusted/untrusted` = lifecycle constraint eligibility
- Enterprise integration: MCP exposes tools, Skill tells DeerFlow how to use them

### 7. Data Boundary Layering
Ten control-plane stores (see Data Layer section). DeerFlow memory is separate and managed by DeerFlow itself.

### 8. DeerFlow Memory: No Strong Audit
- DeerFlow memory is the sole long-term memory source
- SwarmMind does not audit DeerFlow memory internal evolution
- Memory namespace must be constrained by Project runtime instance (no cross-project sharing)
- **No double-write**: DeerFlow memory + separate long-term store = prohibited

### 9. Workflow Knowledge = Control Plane Asset
- Playbooks, SOPs, knowledge packs are versioned assets in WorkflowAssetStore
- Injected into DeerFlow via Project context assembly, never auto-synced with DeerFlow memory

### 10. Approval Is Optional
- Approval layer is off by default
- Only intercepts entire high-risk runs
- If complexity > benefit, remove the approval layer entirely

### 11. Pre-execution Probing Allowed, Not Mandatory
- No `prepare() -> propose() -> execute()` as DeerFlow main-path prerequisite
- Allowed: read-only ops (read files, list dirs, health checks)
- Prohibited: write ops during pre-execution phase

## Target Architecture

```text
Human Supervisor
        |
        v
Supervisor API / UI
       / \
      v   v
Pre-Project Chat
  |- ChatSession
  |- ChatSessionStore
      |
      | promote
      v
Project Workspace
  |- Project Control Plane
  |    |- Broker
  |    |- Router
  |    |- Strategy Table
  |    |- Approval Policy (optional)
  |    |- DeerFlow Gateway
  |    |- Committer
  |
  |- DeerFlow Runtime Kernel
  |    |- lead-agent
  |    |- subagents
  |    |- thread / checkpointer
  |    |- chat / stream
  |    |- uploads / artifacts
  |    |- skills / MCP tools
  |    |- plan_mode
  |    |- memory middleware
  |
  |- Control-plane stores
  |    |- ProjectStore
  |    |- ChatSessionStore
  |    |- AgentTeamTemplateStore
  |    |- ProjectMemberStore
  |    |- RuntimeProfileStore
  |    |- TaskStore
  |    |- RunStore
  |    |- ArtifactStore
  |    |- WorkflowAssetStore
  |    |- AuditLog
  |
  |- Team and workflow layer
       |- Agent Team templates
       |- Project team instances
       |- Workflow templates
       |- Prompt / playbook refs
       |- Runtime profile refs
```

## Current Status

- **Version**: v0.9.0 (DeerFlow-first simplified architecture)
- **Repo**: https://github.com/rongxinzy/SwarmMind
- **Phase**: Phase A (ChatSession + Project + DeerFlow Gateway foundation)
- **Frontend**: shadcn/ui (React 18 + Tailwind CSS + Vite)
- **Backend**: Python (FastAPI)
- **Storage**: SQLite (Phase 1)
- **Python env**: uv

## Implementation Structure

```
swarmmind/                         ← Python package root
├── __init__.py
├── config.py                      ✅ load_dotenv + LLM configuration
├── db.py                          ✅ SQLite schema + health check + seeding + migrations
├── models.py                      ✅ Pydantic models (all database tables)
├── context_broker.py              ✅ dispatch() + keyword routing + strategy table
├── shared_memory.py               ✅ KV store + last-write-wins + 409 retry
├── layered_memory.py              ✅ 4-layer memory (L1_TMP, L2_TEAM, L3_PROJECT, L4_USER_SOUL)
├── renderer.py                    ✅ LLM Status Renderer
├── agents/
│   ├── base.py                    ✅ BaseAgent (abstract base with memory utilities)
│   └── general_agent.py           ✅ GeneralAgent (DeerFlow-driven, handles uncategorized tasks)
├── runtime/
│   ├── bootstrap.py               ✅ DeerFlow Runtime bootstrap + config generation
│   ├── profile.py                 ✅ RuntimeProfile management
│   ├── models.py                  ✅ Runtime data models
│   ├── catalog.py                 ✅ Model catalog for runtime profiles
│   └── errors.py                  ✅ Runtime error types
└── api/
    └── supervisor.py              ✅ FastAPI supervisor REST API

ui/                                ← Supervisor web UI (Vite + React + shadcn/ui)
├── src/
│   └── App.tsx                    ✅ Full supervisor UI
├── vite.config.ts
└── tailwind.config.js

tests/
├── conftest.py                    ✅ Shared test fixtures
├── test_dispatch.py               ✅ Routing, strategy table, unknown goals
├── test_shared_memory.py          ✅ KV store tests
├── test_layered_memory.py         ✅ Layered memory tests
├── test_conversation_titles.py    ✅ ChatSession title generation
├── test_conversation_stream.py    ✅ Streaming conversation tests
└── test_runtime_model_catalog.py  ✅ Runtime model catalog tests
```

## Data Layer

SwarmMind separates 10 types of control-plane data:

| Store | Responsibility |
|-------|---------------|
| **ProjectStore** | Project definitions, scope, constraints, member bindings, run boundaries |
| **ChatSessionStore** | Lightweight chat sessions, title metadata, promotion records |
| **AgentTeamTemplateStore** | Reusable team configuration templates (versioned) |
| **ProjectMemberStore** | Project members, RBAC roles, permission keys |
| **RuntimeProfileStore** | DeerFlow runtime profiles (provider, model catalog, tools, sandbox, secrets) |
| **TaskStore** | Lightweight task metadata (goal, task_kind, routing result) — no large payloads |
| **RunStore** | Execution records, state transitions, event indexes, usage summaries |
| **ArtifactStore** | Reports, code diffs, file outputs, long logs, exports |
| **WorkflowAssetStore** | Playbooks, SOPs, knowledge packs, prompt packs, workflow templates |
| **AuditLog** | Approval results, run event indexes, key decision trails |

**Constraint priority** (highest to lowest): Project constraints > Approval policy > Workflow template rules > Workflow playbook/knowledge pack > DeerFlow memory.

## DeerFlow Runtime Model

### Runtime Interface (DeerFlowGatewayClient)

```python
class DeerFlowGatewayClient:
    def run_turn(
        self, message: str, *,
        thread_id: str,
        stream: bool = False,
        model_name: str | None = None,
        thinking_enabled: bool = True,
        plan_mode: bool = False,
        subagent_enabled: bool = False,
        agent_name: str | None = None,
    ) -> DeerFlowTurnResult: ...
```

DeerFlowTurnResult includes: `final_text`, `events`, `artifacts`, `usage`, `thread_id`, `uploaded_files`, `runtime_flags`.

### DeerFlow Gateway Responsibilities

**Does**: Assemble project context, choose thread strategy, select runtime flags, manage uploads/stream/artifacts, map DeerFlow results to SwarmMind task/artifact/audit records.

**Does not**: Rewrite DeerFlow memory, invent `AgentInterface`/`TeamRuntime` middle layers, invent DeerFlow-native proposal lifecycles.

### Runtime Namespace Isolation

```text
RuntimeNamespace
  - project_id
  - profile_name
  - deerflow_agent_name
  - thread_namespace
  - memory_namespace
  - artifact_namespace
```

Rules: threads cannot cross projects; memory ≥ `project_id + agent_name`; artifacts ≥ `project_id`.

### Runtime Profile vs Instance Separation

- **RuntimeProfile** (control plane): versioned config — provider, model catalog, tools, sandbox, secrets
- **RuntimeInstance** (execution plane): actual running DeerFlow process — endpoint, health, capacity
- One RuntimeProfile can map to multiple RuntimeInstances (pooling/scaling)
- `config.yaml` is a rendered artifact of RuntimeProfile, not the source of truth

### Runtime Evolution Path

| Stage | Model |
|-------|-------|
| MVP / Phase A | Single local DeerFlow Runtime, config generated at startup |
| Phase B | Control-plane manages multiple RuntimeProfiles, sessions dispatched to correct Runtime |
| Phase C | Runtime pool by `runtime_profile_id` |
| Phase D | Runtime Container per `tenant + runtime_profile_id`, sticky project bindings |

## Lifecycle

### ChatSession Path (exploration)

```text
user opens chat → create/reuse ChatSession → DeerFlow run_turn (lightweight) → continue → optional promote to Project
```

### DeerFlow Main Path (execution)

```text
goal → resolve Project boundary → resolve actor + permissions → resolve team instance
  → router selects task_kind → strategy table selects runtime profile
  → assemble project context + workflow assets → optional approval
  → DeerFlow run_turn → commit task/run/artifact/audit records
```

### Multi-user Concurrency

- Minimum isolation unit = `RunRecord` (not Project)
- Thread reuse only within `project_id + selected_profile` boundary
- Same thread cannot have concurrent writes
- Approval/cancel/retry operate on explicit `run_id`

### Failure Semantics

States: `pending | running | success | partial | failure | cancelled`

Guaranteed: failed run → no control-plane metadata committed. `partial` is a first-class state.
Not guaranteed: automatic rollback of external side effects (HTTP calls, file writes).

## Routing & Approval

### Routing

Router outputs one dimension: `task_kind`. Strategy Table maps `task_kind -> DeerFlowRuntimeProfile`.

Current (Phase A):

| Keyword | task_kind | Profile |
|---------|-----------|---------|
| finance/financial/Q3/quarterly/revenue | general | default |
| code/review/PR/git/python/bug | general | default |
| (no match) | general | default |

Future (Phase B+): `code_review`, `deep_research`, `multi_step_delivery`, `finance_analysis` → specific DeerFlow profiles.

### Approval

- Off by default. Only triggered for `high` risk profiles, high-risk external capabilities, or explicit user request.
- Approval object = entire run (not sub-proposals). If complexity > benefit, remove the layer.

## Phase Roadmap

### Phase A (Current)

- [x] SQLite schema + health check + seeding
- [x] Pydantic models for all database tables
- [x] SharedMemory (KV store + conflict resolution)
- [x] ContextBroker (dispatch + keyword routing + strategy table)
- [x] Agent Adapters (BaseAgent, GeneralAgent)
- [x] DeerFlow Runtime bootstrap + config generation
- [x] Runtime profile + model catalog
- [x] Supervisor API (REST endpoints)
- [x] LLM Status Renderer
- [x] Supervisor UI (shadcn/ui, three-tab interface)
- [x] Core tests (dispatch, shared_memory, layered_memory, runtime catalog, conversation)

### Phase B

- [ ] ProjectStore — tasks, approvals, artifacts, audit all on `project_id`
- [ ] ChatSessionStore + Promote to Project (semantic compression)
- [ ] RuntimeProfileStore + RuntimeProvisioner
- [ ] ProjectMemberStore with RBAC
- [ ] RunStore with structured event indexing
- [ ] ArtifactStore for file management
- [ ] AuditLog for compliance tracking
- [ ] DeerFlow memory boundary enforcement
- [ ] DeerFlow `plan_mode` / `subagent` for multi-step tasks
- [ ] Lead-agent as default unified entry

### Phase C

- [ ] AgentTeamTemplateStore + ProjectAgentTeamInstance
- [ ] WorkflowTemplate + WorkflowAssetStore
- [ ] TaskStore with metadata tracking
- [ ] Runtime pool by `runtime_profile_id`
- [ ] Minimal approval layer (only for real high-risk scenarios)

### Phase D

- [ ] Router upgrade: keyword → embedding/classifier
- [ ] ProfileManager with field-level projection
- [ ] Runtime Container: `tenant + runtime_profile_id` isolation pools
- [ ] Evaluate enhanced workflow models (no second execution engine)

## Non-Goals (Prohibited)

The following are excluded from main architecture:

- Multi-engine symmetric abstraction or `AgentInterface` layer
- DeerFlow memory strong audit or per-field replay
- Team/Workflow owning independent long-term memory
- In-process parallel DeerFlow global configs
- Per-session user-uploaded config.yaml
- Dual execution chains (DeerFlow + native LLMClient)
- Control-plane reimplementation of DeerFlow memory/tool/sandbox subsystems
- Cloud skill marketplace, self-evolving skill DAG, universal MCP marketplace
- Automatic compensating transactions

These require separate ADRs if ever needed.

## Python Environment

```bash
uv sync          # install deps
uv run python -m swarmmind.api.supervisor   # run API
```

Secrets → `.env` (gitignored). Copy `.env.example` to `.env` and fill in keys.

## Running

All dev/build commands via `make`:

```bash
make install       # install all deps (uv sync + pnpm install)
make dev           # start both backend + frontend via PM2
make build         # build frontend for production
make typecheck     # TypeScript type check (frontend only)
make test          # run Python backend tests
make logs          # tail PM2 logs
make stop          # stop all services
make status        # show PM2 status
```

PM2 rules: use `pm2 stop` (not `kill -9`). `make restart` recreates frontend for correct cwd.

```bash
make restart-api   # restart backend only
make restart-ui    # recreate frontend only
make restart       # restart both
make backend       # start backend only (first time)
make frontend      # start frontend only (first time)
```

## Coding Rules

- **No hardcoded personal paths** — all paths via env vars or `config.py`
- **Paths must be configurable** — use `os.environ.get()` or config entries
- **Optional dependencies** — non-core features must gracefully degrade
- **Python**: 4-space indent, type hints where practical, snake_case, Ruff (double quotes, 240-char line)
- **TypeScript**: PascalCase components, camelCase helpers, grouped imports, shadcn-style primitives

## LLM Configuration

`.env` (gitignored):
```bash
LLM_PROVIDER=openai
LLM_MODEL=qwen3.5-plus
ANTHROPIC_API_KEY=sk-sp-...
ANTHROPIC_BASE_URL=https://coding.dashscope.aliyuncs.com/v1
```

## Error Handling

- **JSONDecodeError** → rejected proposal with error description
- **EmptyLLMResponse** → rejected proposal with error description
- **StrategyTableMiss** → rejected proposal, logs unknown situation
- **DB conflict (409)** → retries 3x with 100ms backoff, then `SharedMemoryConflict`

## Running Tests

```bash
make test          # uv run pytest tests/ -v
```

## Related Docs

- `docs/architecture.md` — architecture baseline (authoritative)
- `docs/README.md` — documentation index and governance rules
- `docs/enterprise-crm-user-story.md` — scenario validation
- `docs/ui/` — UI wireframes and interaction specs
- `README.md` / `README_zh.md` — public-facing README
