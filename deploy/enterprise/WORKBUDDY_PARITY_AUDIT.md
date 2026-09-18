# WorkBuddy 一致性对照审计（能力 / 交互 / 前端 / UI）

**审计日期**：2026-09-18（V19 更新：SSE / 协作面板 / 成员 ACL）  
**结论先行**：私有化主路径已闭合；V19 补齐审计中的**可做差距**（流式进度、成员角色、共写/资料/记忆/模型/通道/专家团进壳）。刻意不对齐项（Electron / SaaS / 品牌皮肤）仍不算差距。

| 维度 | V18 | V19 后（相对腾讯入门主路径） |
|---|---|---|
| 功能（主路径） | ~98% | **~99%**（+成员 ACL；协作面板进壳） |
| 用户交互 | ~97% | **~99%**（任务 SSE 进度流；非逐字 token 流） |
| 前端结构 | 100% | **100%**（Web 三栏，非 Electron） |
| UI 视觉 | ~95% | **~95%**（非腾讯品牌像素复制） |

---

## 0. 交付边界（刻意不对齐）

| 腾讯 WorkBuddy | 本仓库策略 | 是否算差距 |
|---|---|---|
| 闭源 Electron / QClaw 桌面壳 | Web 三栏壳 `/` + `/ops.html` | 产品选型，**不做** |
| 腾讯云 SaaS / 计费 / 小程序 | Compose / systemd 私有化 | **不做** |
| 腾讯文档 / IMA / 乐享深度集成 | 本地 knowledge / Office 预览 | 等价替代，非像素复制 |
| 官方品牌皮肤 | 知远自有浅色工作台 | **不做** |

---

## 1. 已对齐（主路径 + V19）

| 能力 | 本仓库落点 |
|---|---|
| 登录 / 多租户隔离 | JWT + Casdoor 换发页签 |
| Ask / Plan / Craft | 壳内模式切换 + Policy |
| 任务生命周期 | 新建/搜索/置顶/归档/改名/删除 |
| 真执行 + 人话状态 | `run_task` 默认真跑；中文气泡 |
| Skills 市场安装 | `/api/skills` + 安装 |
| 项目空间 + 技能存入/执行绑定 | `/api/projects*` + shell 选择器 + `bind_skills` |
| **任务 SSE 进度** | V19：`/api/tasks/{id}/events` + `shell_parity.js` 消费 |
| **项目成员 / 角色 ACL** | V19：owner/editor/viewer + 存技能鉴权 + 壳内邀请 |
| **资料 / 共写 / 记忆 / 模型 / 通道 / 专家团** | V19：顶栏入口 + parity 抽屉 |
| 结果区产物/文件/变更/预览/下载 | workspace + Office 预览 |
| 附件上传 | `/upload` |
| 企业组件 | Casdoor / Milvus 可探测（环境依赖） |
| Harbor 评测桥 | smoke / 四子集；sec-full Windows 受限 |

---

## 2. 仍存在的真实差距（收窄后）

### A. 体验层

| 差距 | 说明 | 优先级 |
|---|---|---|
| LLM 逐字 token 流 | 已有步骤/状态 SSE，非模型 token 流式打字 | 中（依赖上游 LLM stream） |
| 桌面系统集成 | 本地文件/托盘/快捷唤起 | 低（选型不做 Electron） |

### B. 协作深度

| 差距 | 说明 |
|---|---|
| 实时共写协同光标 / @评论 | 共写会话已进壳；无 OT/CRDT 级协同 |
| 资料库富浏览器 | 搜索+录入已进壳；非腾讯文档级树浏览 |

### C. 通道与生态

| 差距 | 说明 |
|---|---|
| IM 通道配置向导 | 壳内可看 probe 状态；凭据仍走环境变量 / 运维页 |
| Git worktree 打开向导 | runtime CLI 有，壳无 |

### D. 评测与运维

| 差距 | 说明 |
|---|---|
| Harbor sec-full | Windows 样本/环境异常多；smoke 可用 |
| 公网证书 | 本地 `tls internal`；Let's Encrypt 非门禁 |

### E. 智能深度

| 差距 | 说明 |
|---|---|
| 专家团壳内多席编排 | 壳有入口说明；完整编排仍走 Team CLI/Runtime |
| Agent 轨迹调试时间线 | 有步骤进度条；非腾讯级调试器 |

---

## 3. 一句话对照

- **能私有化交付、能完成「项目挂技能→SSE 看进度→产物」+ 成员/面板**：已对齐。  
- **看起来像腾讯桌面版、有完整云 SaaS 与 OT 共写**：仍有差距，且部分是明确不做。  

验收：
```
python -S scripts/verify_project_space.py
python -S scripts/verify_parity_gaps.py
python -S scripts/verify_v17.py
```
