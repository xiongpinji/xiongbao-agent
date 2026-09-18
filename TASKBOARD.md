# TASKBOARD — WorkBuddy 能力补齐看板

> 对照腾讯 WorkBuddy（专家/SkillHub/连接器/Ask·Plan·Craft/记忆/评测）与本仓库 `octop/contrib/workbuddy`。  
> **执行纪律**：按顺序推进，测绿 → commit → push，中间不请示。

## 已交付（基线）

| ID | 能力 | 状态 |
|---|---|---|
| V1 | wb2octop 245 专家 + Team 运行时 + smoke-50 + 本地 LLM | ✅ |
| V2 | Teach→Routine + CDP + Notion/飞书 + cron tick | ✅ |
| V3 | Goal/Craft MVP + SkillHub 扫描/绑定 | ✅ |
| V4 | 脚本沙箱 + Goal`--skill` + outbox retry | ✅ |
| V5 | Office llm_lite + systemd 文档 + Windows tick | ✅ |

## 差距 → 任务（本轮 V6）

| ID | 差距 | 交付物 | 优先级 | 状态 |
|---|---|---|---|---|
| **V6.1** | Ask / Plan / Craft 工作模式未接线 | `modes/` 装配器 + `modes_cli`；Team/Goal 挂载 | P0 | ✅ |
| **V6.2** | SOUL/USER/MEMORY 未注入系统提示 | `memory/` 加载器，挂到 Team/Goal | P0 | ✅ |
| **V6.3** | 连接器仅 Notion+飞书；vendor 有 100+ | 钉钉/企微 webhook + `connectors_cli` 目录 | P0 | ✅ |
| **V6.4** | 无专家自动路由 | `router/` + `router_cli` tags/关键词匹配 | P0 | ✅ |
| **V6.5** | Bench 仅 office；缺 code/web/sec 列表 | `fetch_bench_subsets.ps1` + `--list-subsets` | P1 | ✅ |
| **V6.6** | 内置 skill（skill-creator 等）未进 SkillHub | SkillCatalog 额外 builtin root | P1 | ✅ |
| **V6.7** | Casdoor/Milvus 仅文档 | `enterprise/` 软探测 stub | P1 | ✅ |
| **V6.8** | 缺一键总验收 | `scripts/verify_all.py` + 文档更新 | P0 | ✅ |

## 明确不做（本轮 / 需外部依赖）

| 项 | 原因 |
|---|---|
| 全量 Harbor Docker verifier | 需 Docker + 上游 harness；llm_lite 已覆盖办公子集 |
| Electron 桌面壳 / 云端 7×24 SaaS | 超出 Octop 自托管边界；systemd 已覆盖保活 |
| 腾讯 CDN 全量镜像 | 用户已决策跳过；vendor 三件套足够 |
| 完整 Nunjucks 引擎渲染 35KB 官方 tpl | 用等价装配器，避免强依赖 Jinja + 复制审查条款全文 |
| Casdoor/Milvus 生产集群部署 | 仅软接线；部署仍走 `deploy/enterprise/` |

## 验收口令

```powershell
python -S scripts\verify_all.py
```

全部步骤 ✓ 后本看板 V6.* 标为 ✅，并更新 ROADMAP / DELIVERABLE / README。
