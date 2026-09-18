# WorkBuddy 一致性对照审计（能力 / 交互 / 前端 / UI）

**审计日期**：2026-09-18（V20 更新：1:1 体验加深）  
**结论先行**：在刻意不做 Electron / SaaS / 品牌皮肤的前提下，**可对齐的产品差距已基本闭合**。V20 补齐流式气泡、轨迹时间线、资料树、仓库 worktree、专家团壳内跑、通道配置向导。

| 维度 | V19 | V20 后（相对腾讯入门主路径） |
|---|---|---|
| 功能（主路径） | ~99% | **~99.5%**（+专家团壳内 / worktree / 资料树） |
| 用户交互 | ~99% | **~99.5%**（步骤 SSE + 助手气泡逐段打字） |
| 前端结构 | 100% | **100%**（Web 三栏） |
| UI 视觉 | ~95% | **~95%**（非腾讯品牌像素复制） |

---

## 0. 交付边界（刻意不对齐）

| 腾讯 WorkBuddy | 本仓库策略 | 是否算差距 |
|---|---|---|
| 闭源 Electron / QClaw 桌面壳 | Web 三栏壳 `/` + `/ops.html` | **不做** |
| 腾讯云 SaaS / 计费 / 小程序 | Compose / systemd 私有化 | **不做** |
| 腾讯文档 / IMA / 乐享深度集成 | 本地 knowledge / library | 等价替代 |
| 官方品牌皮肤 | 知远自有浅色工作台 | **不做** |
| OT/CRDT 实时共写光标 | 共写会话 + 批注追加 | 深度协同不做 |

---

## 1. 已对齐（含 V20）

| 能力 | 落点 |
|---|---|
| 登录 / 多租户 | JWT + Casdoor |
| Ask / Plan / Craft + 真执行 | Policy + `run_task` |
| 项目空间 / 技能绑定 / 成员 ACL | `/api/projects*` |
| 任务 SSE 进度 + **助手气泡流式** | `/events` + `assistant_delta` |
| **Agent 轨迹时间线** | 结果区「轨迹」+ `/run-events` |
| 资料 / 共写 / 记忆 / 模型 | 顶栏 parity 抽屉 |
| **资料库树浏览** | `/api/library` tree + 录入 |
| **通道配置向导** | `/api/channels` + wizard 步骤 |
| **Git worktree 向导** | 顶栏「仓库」+ `/api/worktree` |
| **专家团壳内跑** | `/api/team` + `/api/team/run`（默认同演练） |
| Harbor / 企业探测 | 环境依赖 |

---

## 2. 剩余差距（多为选型或平台）

| 项 | 说明 | 是否继续做 |
|---|---|---|
| 上游 LLM 真 token stream | 当前为结果段流式；非模型原生 SSE token | 可选，绑 provider stream |
| Electron / 托盘 / 本地文件 | 产品选型 | 不做 |
| OT 共写 / @评论 | 共写已进壳 | 不做腾讯文档级 |
| Harbor sec-full on Windows | 环境样本问题 | 平台侧 |
| Let's Encrypt | 非门禁 | 运维可选 |

---

## 3. 一句话

**私有化 WorkBuddy 主路径与壳内协作体验已 1:1 可交付**；剩下是云 SaaS、桌面壳与超深度协同，明确不在范围内。

验收：
```
python -S scripts/verify_v20.py
python -S scripts/verify_parity_gaps.py
python -S scripts/verify_project_space.py
python -S scripts/verify_v17.py
```
