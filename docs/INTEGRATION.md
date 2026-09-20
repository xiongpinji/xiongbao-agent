# 集成手册 — RongXinAI Desktop × Octop 后端 × WorkBuddy Console

本仓库把三个上游融合为一个自托管多 Agent 工作台：

| 层 | 来源 | 角色 |
| --- | --- | --- |
| 后端 | `octop/`（TencentCloud/Octop v1.0.0，MIT） | FastAPI 网关、专家库 / 技能 / 评估、SQLite 或 PostgreSQL |
| Desktop | `vendor/RongXinAI/`（Electron + React + TypeScript） | 桌面应用、本地推理（llama.cpp）、IM 通道 |
| Console | `octop/contrib/workbuddy/console/`（纯 HTML/CSS/JS） | WorkBuddy 品牌 Web 控制台 |

本文档面向 **把整套系统跑起来、部署到生产、做联调** 的工程师。所有命令都在仓库根目录运行。

---

## 1. 用户手册（USER）

> 给最终使用者看的最小操作流程。详情见各子项目 README。

### 1.1 启动 Web 控制台（Console）

最轻量级入口——不需要 Electron 也不需要本地 LLM，只需要一份静态文件即可在浏览器里查看 WorkBuddy 风格 UI。

```bash
# 任意 HTTP 静态服务器（这里用 python 自带的）
python -m http.server 8080 --directory octop/contrib/workbuddy
# 浏览器打开 http://127.0.0.1:8080/console/shell.html
```

### 1.2 启动 Octop 后端 + 控制台

```bash
cd octop
make install-dev          # uv 同步 + 装 dev 依赖
make build-frontend       # 编译 React Dashboard
octop run                 # 默认监听 127.0.0.1:8088
```

浏览器打开 `http://127.0.0.1:8088`，首次进入需要粘贴 `~/octop-login.txt` 里的向导密码。

### 1.3 启动 RongXinAI Desktop（Electron）

需要 Node ≥ 24 且 Bun ≥ 1.3：

```bash
cd vendor/RongXinAI
bun install               # 同时会跑 electron-builder install-app-deps
bun run electron:dev      # 启动 Vite + Electron 热重载
```

应用启动后在 **设置 → 模型服务** 选择本地 llama.cpp 或远程 provider。

### 1.4 把 Desktop 接到 Octop 后端

在 Desktop 设置里填入：

| 字段 | 默认 |
| --- | --- |
| Octop base URL | `http://127.0.0.1:8088` |
| JWT | `octop user login` 后从用户菜单复制 |
| Agent ID | 在 Octop Dashboard 创建后取得 |

Desktop 的 IM 通道（飞书 / 企微 / 钉钉 / 微信 / 邮件）配置完成后，IM 收到的消息会自动通过 `OctopChatHandler` → `OctopChatClient` 走 WebSocket（`/api/agents/{agent_id}/chat/ws`）发给 Octop，无需再走远程 LLM。

---

## 2. 开发者手册（DEV）

### 2.1 环境

| 工具 | 版本 |
| --- | --- |
| Python | 3.12+ |
| Node.js | ≥ 24 < 25 |
| Bun | ≥ 1.3（RongXinAI 包管理器） |
| uv | ≥ 0.11（Octop 包管理器） |
| Windows | PortableGit（如要在 Windows 构建） |

### 2.2 一次性安装

```bash
cd octop
make install-hooks        # 启用 .githooks/pre-commit（format-all + lint + typecheck + dashboard build + test）
make install-dev          # uv sync 等价于 uv pip install -e ".[dev]"
cd ../vendor/RongXinAI
bun install
```

### 2.3 跑测试

| 范围 | 命令 |
| --- | --- |
| Octop 后端 ship bar | `cd octop && make all` |
| Octop 后端单测 | `cd octop && uv run pytest -m "not live"` |
| Octop 后端 live 测 | `cd octop && uv run pytest -m live`（需要真实 LLM 凭证） |
| RongXinAI renderer | `cd vendor/RongXinAI && npm test` |
| Console Web E2E | `node octop/contrib/workbuddy/console/e2e/run-smoke.mjs` |
| Octop 性能基线 | `cd octop && uv run python scripts/perf_baseline.py` |

性能门禁与历史指标见 [`docs/performance-baselines.md`](performance-baselines.md)。

### 2.4 常用代码入口

| 想做什么 | 看哪里 |
| --- | --- |
| 加一个新 REST 端点 | `octop/src/octop/api/routers/` + `octop/docs/api.md` |
| 加一个新数据库迁移 | `octop/src/octop/infra/db/migrations/00N_xxx.sql`（成对 `.pg.sql`） |
| 加一个新 Worker 任务 | `vendor/RongXinAI/src/main/libs/agentEngine/`（遵守 `AGENTS.md` 中 Worker 线程约束） |
| 加一个新 Skill | `octop/src/octop/infra/skills/` 或 WorkBuddy skill 包内嵌 |
| 接入新 IM 平台 | `octop/src/octop/infra/gateway/bot_creators/` |
| 改品牌 / 主题 | `vendor/RongXinAI/DESIGN.md` 是宪法；改动必须先读它 |
| 跨层联调（Desktop ↔ Octop） | `vendor/RongXinAI/src/main/libs/octopBridge/` |

### 2.5 跨平台注意

- 不要假设 POSIX-only 路径，参见 `octop/AGENTS.md §7`。
- Electron 的原生模块（`better-sqlite3`、`node-pty`）变更后必须跑
  `npm run rebuild:electron-native`。
- i18n：服务端走 `octop/src/octop/i18n/*.json`；Desktop 走 `vendor/RongXinAI/src/renderer/services/i18n.ts`。

---

## 3. 部署手册（OPS）

### 3.1 单机开发 / 自托管

```bash
# 后端
cd octop && make build && pip install dist/octop-*.whl
octop run                 # 监听 0.0.0.0:8088（如需对外，配置 OCTOP_BIND_HOST）

# Desktop（pack 模式）
cd vendor/RongXinAI && npm run dist:win
```

### 3.2 生产 Docker Compose

参见 `octop/docker/README.md` 与 `deploy/docker-compose.workbuddy.yml`。
Compose 同时拉起 Octop / Casdoor / Milvus / Postgres，**默认监听 8088**，TLS 由前置反向代理处理。

### 3.3 企业加固清单

- [ ] 改默认管理员密码 + JWT secret（`OCTOP_JWT_SECRET`）
- [ ] 配置 PostgreSQL 后端（`OCTOP_DATABASE_DRIVER=postgresql`），不要用 SQLite 跑多副本
- [ ] 启用 Let's Encrypt：`infra/setup/tls/`
- [ ] 启用审计日志：`infra/agents/audit_log.py`（默认开启）
- [ ] Skill 沙箱白名单：见 `octop/src/octop/infra/skills/sandbox.py`
- [ ] 备份策略：定时 `octop backup create`，目标 COS / S3
- [ ] IM 通道出站限速 + bot 上限（详见 `infra/gateway/bot_creators/`）

### 3.4 灰度 / 回滚

- 服务端：`octop` 是单进程 FastAPI；用 systemd 或 Compose 控制滚动重启。
- Desktop：通过 `vendor/RongXinAI/scripts/prepare-update-release.cjs` 生成增量更新包，旧版本会自动覆盖安装。
- 数据库：每次迁移前 `octop backup create`；回滚用 `octop backup restore --to <id>`（仅支持 0.x → 0.x 向前兼容；详细迁移矩阵见 [P2-9 数据迁移回滚](#)——此节将在 P2-9 完成时补齐）。

### 3.5 监控

- 后端：`/api/metrics`（Prometheus 格式）默认开启
- Desktop：内置 `startupProfiler` 写主进程阶段耗时日志；`memory-leak-check.mjs` 已在 GitHub Actions nightly 跑
- 日志：Octop 走 `octop.log`（按日轮转）；Desktop 走 electron-log

---

## 4. 联调常见问题

| 现象 | 排查 |
| --- | --- |
| Desktop 连不上 Octop | 检查 `OCTOP_BIND_HOST`；Desktop 默认连 `127.0.0.1:8088`，非本机要换成 `host.docker.internal` 或 LAN IP |
| IM 消息没回 | 看 `IMChatHandler` / `OctopChatHandler` 日志，确认 `WebSocketCtor` 在测试环境是 fake、生产是 `ws` |
| Console 一直转圈 | `Octop base URL` 配错；F12 看 Network，找 `/api/agents/me/sessions` 是否 200 |
| Skill 报 sandbox violation | `octop skill audit <skill_id>`；白名单脚本必须放 `scripts/` 下且不能 `..` |
| Electron 启动崩溃 | `npm run rebuild:electron-native`；Windows 还要 PortableGit |

---

## 5. 文档地图

| 文档 | 内容 |
| --- | --- |
| [`README.md`](../README.md) | 项目总览 + 交付范围（V1–V7） |
| [`octop/README.md`](../octop/README.md) / [`octop/README_CN.md`](../octop/README_CN.md) | Octop 后端深度文档 |
| [`octop/docs/user-guide.md`](../octop/docs/user-guide.md) | Octop 用户操作手册 |
| [`octop/docs/architecture.md`](../octop/docs/architecture.md) | Octop 架构 |
| [`octop/docs/api.md`](../octop/docs/api.md) | API 参考 |
| [`vendor/RongXinAI/AGENTS.md`](../vendor/RongXinAI/AGENTS.md) / `DESIGN.md` | RongXinAI 开发与设计宪法 |
| [`docs/performance-baselines.md`](performance-baselines.md) | 性能基线 / 门禁 |
| [`octop/contrib/workbuddy/console/e2e/README.md`](../octop/contrib/workbuddy/console/e2e/README.md) | Console E2E 说明 |
