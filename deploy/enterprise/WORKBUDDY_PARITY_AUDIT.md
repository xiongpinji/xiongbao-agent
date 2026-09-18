# WorkBuddy 一致性对照审计（能力 / 交互 / 前端 / UI）

**审计日期**：2026-09-18  
**对照来源**：腾讯云 WorkBuddy Enterprise 入门指南（任务/对话/结果三区）、WorkBuddy 文档 Sidebar / Results；本仓库 V1–V11 实现与产品边界（`ROADMAP.md` / `TASKBOARD.md`）。  
**结论先行**：**后端与 CLI 能力面大体对齐（能力等价）**；**用户端交互、前端架构、UI 视觉与腾讯桌面壳不一致**——这是立项边界，不是漏做的同一层交付。

---

## 0. 交付边界（先读）

| 腾讯 WorkBuddy | 本仓库明确策略 |
|---|---|
| 闭源 Electron / QClaw 桌面壳 | **不复刻**；用 CLI + 轻量 Console + Octop |
| 腾讯云 SaaS / 计费 / 小程序 | **不做** |
| 左栏任务 + 中栏对话 + 右栏结果 三栏 UI | **不做像素级复制** |
| 私有化多租户隔离 | **V11 已交付（P0）** |

因此：「功能一致」= **能力可达成**；「交互/前端/UI 一致」= **桌面产品体验一致** → 后者 **当前不一致，且未列入 V11 Done**。

---

## 1. 功能（能力面）对照

| WorkBuddy 能力 | 本仓库落点 | 一致度 |
|---|---|---|
| 创建/管理任务、状态机 | `task/` + `task_cli` + Console `/api/tasks` | ✅ 高（文件系统任务） |
| Ask / Plan / Craft 模式 | `modes/` + task.mode | ✅ 高（模式字段与组装） |
| 任务执行 / Goal | `goal/` + `runtime/task_runner` | ✅ 中高（CLI/runtime；非桌面内嵌执行流） |
| Skills 市场 + 扫描安装 | `skills/market` + `runtime/skill_register` | ✅ 中高（目录/扫描；无官方商店 UI） |
| 权限策略 | `security/policy` + runtime 门禁 | ✅ 高 |
| 记忆 / 本地知识库 | `memory/` + `knowledge/` | ✅ 中高（本地；Milvus 可选） |
| 资料库 / 灵感 / 共写 | `library` / `inspiration` / `cowrite` | ✅ 高（CLI parity 面） |
| 微信/QQ 等国内 IM | `connectors/china_im` + channel_bridge | ✅ 中（桥接/出站；非官方客户端内嵌） |
| 钉钉/企微 | messaging connectors | ✅ 中高 |
| Teach / Routine 自动化 | `teach/` + `routine/` + cron tick | ✅ 高（本仓库增强面） |
| Harbor / bench 评分 | Harbor 桥 + dry-run | ⚠️ 中（dry/harness；全量 live 非门禁） |
| 企业 SSO | Casdoor 换发 JWT | ⚠️ 已接线，凭据未配则为暗 |
| 向量库租户隔离 | Milvus `wb_{tid}` | ⚠️ 已接线，URI 未配则为暗 |
| 多租户隔离 / 备份 | `tenant/*` + go-live | ✅ 高（相对 SaaS 的私有化等价） |
| 结果产物 Artifacts 面板 | `office/artifacts` + 文件系统 | ⚠️ 有产物能力，**无右侧四 Tab UI** |
| 工作空间 / 置顶 / 归档侧栏 | project/space + task 元数据部分 | ⚠️ 数据可存，**无侧栏交互** |

**能力结论**：主线办公 Agent 能力（任务、模式、技能、连接器、知识、共写、多租户）在 **引擎/CLI 层对齐**；缺的是 **桌面壳把这些能力编成同一套用户旅程**。

---

## 2. 用户端交互对照

| 腾讯交互旅程 | 本仓库现状 | 一致？ |
|---|---|---|
| 侧栏「新建任务」→ 一句话开聊 | CLI `task_cli` / API；Console 仅列表 | ❌ |
| 中栏持续对话、追问、上传、中断 | Goal/runtime 文本流在后端；无对话主界面 | ❌ |
| 右栏产物 / 全部文件 / 变更 / 预览 | 文件落盘可查；无四 Tab 结果区 | ❌ |
| 多任务并行切换不丢上下文 | 多 task 目录并行可行；无任务面板切换 UX | ⚠️ 能力有、交互无 |
| Skills 市场点选安装 | CLI 扫描安装；Console 只展示 JSON/表 | ⚠️ |
| 搜索/筛选/置顶/归档任务 | API 列表无筛选 UI | ❌ |
| 运维：租户登录看本户任务 | Console 现已补 JWT 登录表单 | ✅ 运维交互可用 |

**交互结论**：**终端用户旅程 ≠ WorkBuddy 桌面**；**运维/管理员旅程**（开户、鉴权、隔离验、备份）已闭环。

---

## 3. 前端架构对照

| 维度 | 腾讯 WorkBuddy | 本仓库 |
|---|---|---|
| 技术 | Electron 桌面 + 富客户端 | 单页 `console/index.html` + 静态 fetch |
| 路由/状态 | 工作区 + 任务会话状态机 UI | Tab 切换 + raw JSON |
| 鉴权 UI | 账号体系 / 企业登录 | JWT 登录条（tenant/user/api_key） |
| 与 Octop Dashboard | — | **明确不 fork** React Dashboard |

**前端结论**：**不是同一类前端**；不可声称「前端一致」。

---

## 4. UI 视觉对照

| 维度 | 腾讯 | 本仓库 Console |
|---|---|---|
| 布局 | 左 / 中 / 右 三栏 | 顶栏 Tab + 卡片 + 表格/JSON |
| 主题 | 产品浅色/品牌桌面风 | 深色运维风（自研） |
| 品牌 | WorkBuddy / 腾讯云 | 「知远 · WorkBuddy Console」 |
| 结果预览 | 内置浏览器 / 文档预览 | 无 |

**UI 结论**：**不一致**。若要「看起来像 WorkBuddy」，需单独立项 **V12 用户壳**（仍建议不碰闭源 Electron，而做 Web 三栏或接入现有 Octop Chat 面）。

---

## 5. 一致性矩阵（汇总）

| 维度 | 评分 | 说明 |
|---|---|---|
| 功能（能力） | **约 75–85%** | 引擎/CLI 对齐；商店 UI、全量 Harbor live、官方 IM 客户端除外 |
| 用户交互 | **约 20–30%** | 缺三栏任务对话结果闭环 |
| 前端 | **约 15%** | 运维页 ≠ 产品壳 |
| UI | **约 10%** | 视觉与布局均不等价 |
| 多租户私有化（本轮主线） | **≥95% P0** | 与「多家客户共用实例」目标一致 |

---

## 6. 建议的下一板（若要「交互也像」）

仅在业务明确要求「用户端对齐桌面」时启动 **V12 User Shell**：

1. Web 三栏：任务侧栏 / 对话中栏 / 结果右栏（Artifacts·Files·Diff·Preview）
2. 复用现有 `task`/`goal`/`runtime` API，禁止重写引擎
3. 登录接现有 JWT / Casdoor
4. **仍不**复刻 Electron、计费、小程序

当前主线（多租户可交付）**不必**阻塞在 V12。

---

## 7. 本轮已落地的运维补强

- Console：鉴权开启时显示登录框，请求带 `Authorization: Bearer`
- Compose prod：透传 `WB_LLM_*` 与 `OCTOP_MILVUS_URI`
- 开户/异地备份手册：`deploy/enterprise/CUSTOMER_ONBOARD.md`
