# 熊宝 Agent 接通 octop run — 设计文档

> 状态：**待用户审阅**
> 拟定日期：2026-09-20
> 范围：第一阶段，对标 WorkBuddy 的改造 + 熊宝自研 UI 全部接通到 `octop run`

---

## 一、产品定位（来自用户描述）

```
熊宝 Agent（XiongBao Agent）— 我们的商品
├─ 底座：octop（基于其二次开发，借用引擎 / harness / 后端）
├─ 第一阶段目标：对标 WorkBuddy（功能上改造升级）
├─ 前端：熊宝 Agent 自己的 UI（不是 octop 的 React SPA，也不是 WorkBuddy 开源版）
│   ├─ 视觉、布局、交互、展现：参考了 WorkBuddy
│   └─ 设计代码、品牌资产 100% 熊宝自有（contrib/workbuddy/console/）
└─ 部署形态：单一产物 = `octop run`（用户拍板：merge-into-octop-run）
```

## 二、当前事实（已校验）

| 资产 | 状态 |
|---|---|
| `octop/contrib/workbuddy/console/` | **熊宝 UI 全部资产就绪**（shell.html 75KB、5 个 CSS、tokens.css、icons.svg、brand assets） |
| `octop/contrib/workbuddy/console/SUMMARY.md` | UI 改动总结在 |
| `octop/contrib/workbuddy/{tenant,project,task,skills,connectors,runtime,console_parity_api}.py` | **改造的对标 WorkBuddy 后端就绪**（30+ 文件，纯 stdlib + 5 个第三方依赖：PIL/docx/openpyxl/pptx） |
| `octop/contrib/workbuddy/console_server.py` | 自带 stdlib HTTP 服务，但**没人启动它**（8010 端口未在 listen） |
| `octop/run` 现在在 8088 跑 | 加载 `octop/dashboard/` React SPA，**完全是 octop 原生 UI** |
| `octop/dashboard/` React SPA | 跟熊宝品牌没关系，**应该被替换或并存** |
| octop `users` 表（sqlite） | `admin / Admin@2026` 已建（用户拍板：打通） |
| `artifacts/tenants/_registry.json` | 不存在 → 没人能用 workbuddy |

**关键事实（grep 已验证）：`octop/contrib/workbuddy/` 下 0 处 `import octop.*`** —— workbuddy 是完全独立的代码包，不依赖 octop 主包。

## 三、目标架构（接好后）

```
                          单一部署产物
                ┌──────────────────────────────┐
                │       octop run (8088)        │
                │                              │
   浏览器  ───────▶ │  路由分发（octop.api.app）  │
   (熊宝 UI)        │                              │
                │  /             → 熊宝 shell.html  │
                │  /console/*    → 熊宝静态资源      │
                │  /ops          → 熊宝 ops.html    │
                │  /api/auth/*   → octop 用户表      │
                │  /api/agents/* → octop 原生能力    │
                │  /api/xb/*     → 熊宝改造 API（NEW）│
                │  /api/ws/*     → harness SSE      │
                │                              │
                │  ┌────────────────────────┐  │
                │  │ 熊宝 UI HTML/CSS/JS    │  │
                │  │ (contrib/workbuddy/   │  │
                │  │  console/)            │  │
                │  └────────────────────────┘  │
                │  ┌────────────────────────┐  │
                │  │ 熊宝改造路由 (NEW)      │  │
                │  │ octop.api.routers.xb   │  │
                │  └────────────────────────┘  │
                │  ┌────────────────────────┐  │
                │  │ octop 原生能力（保留）  │  │
                │  │ - UserManager (admin)  │  │
                │  │ - agents / harness     │  │
                │  │ - providers / skills   │  │
                │  │ - connectors / channels│  │
                │  │ - cron / settings ...  │  │
                │  └────────────────────────┘  │
                └──────────────────────────────┘
                              │
                              ▼
                    octop.sqlite (WAL)
                    ├─ users（admin/Admin@2026）
                    ├─ agents / threads / messages
                    ├─ skills / providers / connectors
                    └─ ...（octop 原有所有表）
```

注意：**改造路由（`/api/xb/*`）的 handler 全部复用** `octop.contrib.workbuddy.{tenant,project,task,skills,connectors,runtime,console_parity_api}` 这些**已就绪的代码**，只把它们**挂到 FastAPI 上**+ **去掉它们独立的租户 JSON**，让它们读 octop 的 sqlite。

## 四、对比 WorkBuddy 的功能映射（改造清单）

> 以下接口是 `contrib/workbuddy/console_parity_api.py` 和 `console_server.py` 已经实现的（`/` = "对标了"）

| 域 | 熊宝实现位置 | 对标 WorkBuddy | 暴露路径（挂到 octop 后）|
|---|---|---|---|
| **认证** | `tenant/auth.py` | WB 会话登录 | **复用 octop 原生** `/api/auth/login` |
| **租户** | `tenant/registry.py` | WB 多 Workspace | `/api/xb/tenants/*`（admin only）|
| **任务流** | `task/`, `runtime/` | WB 任务流 | `/api/xb/tasks`, `/api/xb/tasks/{id}/run` |
| **项目空间** | `project/` | WB Projects | `/api/xb/projects`, `/api/xb/projects/{id}/skills` |
| **Skills** | `skills/` | WB Skills 市场 | `/api/xb/skills`, `/api/xb/skills/install` |
| **连接器** | `connectors/` | WB 第三方连接 | `/api/xb/connectors`, `/api/xb/connectors/{id}/probe` |
| **Hub 状态** | `hub.py` | WB Hub | `/api/xb/hub` |
| **Ops** | `ops_health.py` | WB 健康台 | `/api/xb/ops`, `/api/xb/ops/restart` |
| **企业版** | `enterprise/probe.py`, `enterprise/casdoor.py` | WB 企业功能 | `/api/xb/enterprise` |
| **Office 解析** | `office/artifacts.py`, `office_preview.py` | WB 文档预览 | `/api/xb/office/preview` |
| **Bench** | `bench/harbor.py`, `bench/runner.py` | WB 自评测 | `/api/xb/harbor/{status,dry-run,score}` |

## 五、关键设计决策

### D1. 账号体系 — 用 octop 原生，弃 workbuddy 独立租户

**决策**：复用 octop 的 `users` 表 + JWT（`api/routers/auth.py` 已实现）。
**原因**：
- 用户已建 `admin / Admin@2026`，登录一次能进所有界面
- octop 的 `UserManager` 已支持 argon2 + JWT + 权限
- workbuddy 的 `tenant/registry.py` 整套 JSON 注册 → **废止**

**改动**：
- `octop.contrib.workbuddy.tenant.registry` → 改为"读 octop 的 users/permissions"薄包装
- `tenant/auth.py:issue_token/verify_token` → **删除**，直接用 `octop.api.deps.sign_token`
- 改造路由的 `Depends(get_current_user)` 复用 `octop.api.deps.current_user`

### D2. UI 入口 — 熊宝 UI 默认首页，octop React SPA 保留为"运维模式"

**决策**：
- `GET /` → 301 → `/shell.html`（熊宝主壳）
- `GET /ops` → `/ops.html`（熊宝运维台，**取代** octop 的 `dashboard/`）
- `GET /console/{anything}` → 静态资源
- `GET /legacy-dashboard/*` → octop 原生 React SPA（**保留**，作为内部开发者视角，不影响产品用户）
- `enable_dashboard` 配置：`octop.json` 里新加 `dashboard_mode: "xiongbao" | "legacy"`，默认 `"xiongbao"`

**改动**：
- `api/app.py:288 spa_fallback` → 改为先尝试熊宝 UI，再 fallback 到 octop dashboard
- `api/app.py:289 dashboard_dir` → 在 `dashboard_mode == "xiongbao"` 时改为 `octop/contrib/workbuddy/console`

### D3. 改造 API 挂载 — 新建 `octop.api.routers.xb` 适配层

**决策**：**不修改** `contrib/workbuddy/` 任何源码。新建适配层：
```
octop/api/routers/xb/
├─ __init__.py
├─ tasks.py        # /api/xb/tasks/*，内部调用 octop.contrib.workbuddy.task.TaskStore
├─ projects.py     # /api/xb/projects/*
├─ skills.py       # /api/xb/skills/*
├─ connectors.py   # /api/xb/connectors/*
├─ ops.py          # /api/xb/ops, /api/xb/hub, /api/xb/enterprise
├─ tenant.py       # /api/xb/tenants/*（admin）
├─ office.py       # /api/xb/office/*
├─ bench.py        # /api/xb/harbor/*
└─ deps.py         # 共享：当前用户的租户隔离 / 配额检查
```

**依赖图**：
```
octop/api/routers/xb/tasks.py
  → Depends(octop.api.deps.current_user)        # octop JWT
  → 调用 octop.contrib.workbuddy.task.TaskStore  # 复用存储
  → 路径映射：XB-/api/xb/tasks ↔ octop storage ~/octop/users/<uid>/tasks/
```

**租户隔离**：把 workbuddy 的"按 tenant_id 隔离"改成"按 octop user_id 隔离"，存储根目录：
```
~/.octop/users/<user_id>/xb/tasks/
~/.octop/users/<user_id>/xb/projects/
~/.octop/users/<user_id>/xb/skills-installed/
```

### D4. Skills 市场 — 双轨

**决策**：
- `/api/skills`（octop 原生）→ 已有 `octop.api.routers.skills`
- `/api/xb/skills`（熊宝改造）→ 新路由，调 `octop.contrib.workbuddy.skills.SkillCatalog`
- 两者并存，UI 上让熊宝 UI 默认走 `/api/xb/skills`

### D5. 任务执行引擎 — 复用 octop harness

**决策**：`/api/xb/tasks/{id}/run` 内部最终调到 octop 的 `harness-agent`（已经有 LLM provider 链路）。
**改动**：
- `octop.contrib.workbuddy.runtime.task_runner.run_task()` 内核改为 `await harness.run(agent_id, message)`
- 之前的 stdlib 独立路径只用于 `dry_run=True`（不调 LLM）

### D6. 静态资源 — `octop.contrib.workbuddy.console` 作为只读静态目录

**决策**：在 `api/app.py` 增加：
```python
if cfg.dashboard_mode == "xiongbao":
    console_dir = Path("octop/contrib/workbuddy/console")
    app.mount("/console", StaticFiles(directory=console_dir, html=True), name="xb-console")
    # 兼容 shell.html 引用的 /tokens.css, /shell.css, /shell_pages.js 等绝对路径
    # 由 spa_fallback 把 "/" 映射到 shell.html，"ops" 映射到 ops.html
```

### D7. 配置项 — `config.json` 新增

```json
{
  "dashboard_mode": "xiongbao",     // "xiongbao" | "legacy"
  "xiongbao": {
    "console_path": "octop/contrib/workbuddy/console",
    "users_root": "~/.octop/users",  // 每用户子目录
    "enable_bench": false,           // /api/xb/harbor/*
    "enable_office_preview": true
  }
}
```

## 六、实施步骤（建议 5 个 PR，每个 PR 可独立 ship）

### PR1. 打通账号 + 静态 UI（最小可点）
- [ ] `octop/api/app.py`：新增 `dashboard_mode == "xiongbao"` 分支，挂 `console/` 静态目录
- [ ] `octop/api/app.py`：根路由 `/` 在 xiongbao 模式返回 `shell.html`
- [ ] `octop/api/app.py`：`/ops` 返回 `ops.html`
- [ ] `octop/config.py`：加 `dashboard_mode` 字段
- [ ] 改写 `~/.octop/config.json` 为 `"dashboard_mode": "xiongbao"`
- **验收**：`octop run`，浏览器 `http://127.0.0.1:8088/` 显示金色深色登录页 → 输 `admin / Admin@2026` 登入（**登录走 octop 原生 /api/auth/login**，UI 调 `/api/auth/me`）

### PR2. 改造 API 适配层（任务 + 项目）
- [ ] 新建 `octop/api/routers/xb/__init__.py`
- [ ] 新建 `octop/api/routers/xb/deps.py`：从 octop `current_user` 派生 `xb_roots = ~/.octop/users/<uid>/xb/`
- [ ] 新建 `octop/api/routers/xb/tasks.py`：包 `octop.contrib.workbuddy.task.TaskStore`，路径 `/api/xb/tasks`
- [ ] 新建 `octop/api/routers/xb/projects.py`：包 `octop.contrib.workbuddy.project.ProjectSpace`
- [ ] `api/app.py` 注册 `_RouterMount(xb_router, "/api/xb", ["xiongbao"])`
- [ ] **不动 `contrib/workbuddy/` 源码**（如果需要薄改，记 PR3 集中处理）
- **验收**：浏览器里能看到任务列表、能建项目、能跑 dry-run 任务

### PR3. 改造 API 适配层（Skills + Connectors + Hub/Ops/Enterprise）
- [ ] `xb/skills.py`、`xb/connectors.py`、`xb/ops.py`、`xb/tenant.py`、`xb/office.py`、`xb/bench.py`
- [ ] 复用 octop 原生的 RBAC（admin 才能装 Skill / 看 enterprise）
- [ ] 弃用 `workbuddy/tenant/auth.py`，所有 `_auth_context` 改为 `Depends(current_user)`
- **验收**：UI 上 Skills 市场能浏览、能装、能启；连接器 probe 能跑

### PR4. 任务执行引擎 — 接到 octop harness
- [ ] `octop.contrib.workbuddy.runtime.task_runner.run_task` 接入 harness
- [ ] `octop/api/routers/xb/tasks.py` 的 `/run` 改为真跑 LLM
- [ ] SSE 流：`/api/xb/tasks/{id}/events` 透传 harness 的 message stream
- **验收**：建任务 → 真跑 → UI 流式显示模型输出 → 落 events.jsonl

### PR5. 清理 + 文档
- [ ] 删除 `octop/contrib/workbuddy/console_server.py`（**前提**：确认没人外部调用）
- [ ] 删除 `octop/contrib/workbuddy/tenant/registry.py` 的写路径（保留读路径给 stats）
- [ ] `docs/xiongbao-merge-design.md` 更新实施完成状态
- [ ] `octop/AGENTS.md` §5、§10 加一句："熊宝 Agent 是基于 octop 的产品，UI 与改造路由在 contrib/workbuddy/ 下，统一由 octop run 暴露"
- [ ] `octop/contrib/workbuddy/console/SUMMARY.md` 加一段："如何接入 octop run"

## 七、风险 & 边界

| 风险 | 缓解 |
|---|---|
| `contrib/workbuddy/` 内部还引用 `tenant/registry.py` | 在 PR3 前先做只读改造；存储根从 `artifacts/tenants/<tid>/` 改成 `~/.octop/users/<uid>/xb/` |
| 熊宝 UI 假设了 `octop.contrib.workbuddy.tenant.auth.issue_token` 风格 | UI 内有现成 `login.js` 走 `/api/auth/login` 即可，**改 UI 不在 PR1 范围**（UI 已用 `Authorization: Bearer` 头） |
| 改造路由与 octop 原生路由路径冲突 | 用 `/api/xb/*` 前缀隔离 |
| `console_server.py` 外被调用（脚本/CI） | PR5 之前留兼容 shim；`/api/auth/login` 入口不变 |
| admin 权限过大 | octop 原生 RBAC 已支持 `effective_permissions`；熊宝 admin 操作走 `Depends(current_user)` 加 `if user.role != "admin"` |
| 文件系统 vs 数据库存储 | 任务/项目仍用文件系统（workbuddy 的设计）+ 索引表用 octop 的 sqlite；不在本设计范围扩 |

## 八、待用户决策项

下列决策在本次审阅后确认：

| # | 决策 | 默认提议 |
|---|---|---|
| Q1 | `/api/xb/*` 还是直接 `/api/*`（覆盖 octop 原生）？ | **`/api/xb/*`**（避免和 octop 原生冲突，可渐进迁移） |
| Q2 | 是否在第一阶段就启用 `enable_bench` / `enable_office_preview`？ | **默认关**，等 PR5 启用 |
| Q3 | 老的 `octop/dashboard/` React SPA 是删还是保留为 `/legacy-dashboard`？ | **保留**（内部开发者用，不影响产品用户） |
| Q4 | 是否在 PR1 就修改 `~/.octop/config.json` 把 `dashboard_mode` 设成 `xiongbao`？ | **是**，否则 8088 还是 octop UI |
| Q5 | `console_server.py` 删还是留作 shim？ | **PR5 删除**（前 4 个 PR 期间不启它即可） |

## 九、不在本设计范围

- ❌ 熊宝 UI 的视觉细节调整（已经在 SUMMARY.md 里完整记录）
- ❌ WorkBuddy expert 转换器 `converter.py`（独立工具，与接通无关）
- ❌ Team / Teach / Cowrite 子模块（功能独立，先不接通 octop run）
- ❌ 替换 octop 原生的 harness（继续用 octop 现有 harness）
- ❌ 把熊宝 UI 重写到 React（明确不做，熊宝 UI 是 HTML + CSS + JS）
