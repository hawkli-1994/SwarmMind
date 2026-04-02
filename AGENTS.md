# SwarmMind — Agents Documentation

**AI agent team operating system. v0.9.0 — DeerFlow-first simplified architecture.**

> **Architecture baseline**: `docs/architecture.md` is the single source of truth.
> If code conflicts with architecture, code must be refactored.

## Architecture References

核心架构已完整写入以下文档，AGENTS.md 不再重复：

| Topic | Document |
|-------|----------|
| 术语表（禁止裸用 `Agent`） | `docs/architecture.md` §1 |
| 核心原则（11 条） | `docs/architecture.md` §2 |
| 目标架构图 | `docs/architecture.md` §3 |
| DeerFlow 执行模型（Gateway、Namespace、Profile/Instance） | `docs/architecture.md` §4 |
| 控制面数据边界（10 Store） | `docs/architecture.md` §5 |
| 生命周期与协作（ChatSession / 主路径 / 并发 / 失败） | `docs/architecture.md` §6 |
| 路由与审批 | `docs/architecture.md` §7 |
| 非目标 | `docs/architecture.md` §8 |
| 实施路线（Phase A-D） | `docs/architecture.md` §9 |
| 目标目录结构 | `docs/architecture.md` §10 |
| UI 线框与交互规则 | `docs/ui/` |
| 场景验证 | `docs/enterprise-crm-user-story.md` |
| 文档治理规则 | `docs/README.md` |

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
│   └── general_agent.py           ✅ DeerFlowRuntimeAdapter (DeerFlow-driven adapter, compat alias: GeneralAgent)
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

## Phase Roadmap

### Phase A (Current)

- [x] SQLite schema + health check + seeding
- [x] Pydantic models for all database tables
- [x] SharedMemory (KV store + conflict resolution)
- [x] ContextBroker (dispatch + keyword routing + strategy table)
- [x] Agent Adapters (BaseAgent, DeerFlowRuntimeAdapter)
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
