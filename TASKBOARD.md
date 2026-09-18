# TASKBOARD — WorkBuddy 剩余全量对齐（V9）

> 基线：V1–V8 已交付（能力对齐 + Harbor dry-run + Compose/Console 常驻）。  
> 本板覆盖：**官方文档功能矩阵中仍缺的等价能力**。  
> **边界不变**：不复刻 Electron/QClaw、腾讯云 SaaS、小程序/移动端、计费积分。

## V9 任务拆解（一次性）

| ID | 交付物 | 验收 | 状态 |
|---|---|---|---|
| V9.1 | `task/` 生命周期：create/list/get/append/complete + CLI | 单测 + `task_cli` | ✅ |
| V9.2 | `security/policy` 权限模式（ask/plan/craft/sandbox） | 策略读写 + CLI | ✅ |
| V9.3 | `data/` 工作区导出导入 zip/jsonl | export/import 往返 | ✅ |
| V9.4 | `models_profile/` 模型档案（本地 OpenAI 兼容） | profile get/set/list | ✅ |
| V9.5 | `gitwork/worktree` 并行任务目录隔离 | create/list/remove | ✅ |
| V9.6 | 微信/QQ 连接器（webhook 出站 + 入站 inbox JSONL） | probe + Fake HTTP | ✅ |
| V9.7 | `library/` 资料库索引 + 轻量发布（静态 html） | index/publish | ✅ |
| V9.8 | `inspiration/` + Buddy App 模板脚手架 | list/scaffold | ✅ |
| V9.9 | `knowledge/` 本地 KB（目录切片 + 可选 Milvus upsert） | ingest/search | ✅ |
| V9.10 | `cowrite/` 人机双写会话 | start/append/export | ✅ |
| V9.11 | `channel_bridge` 入站消息 → Task（门禁） | dry 路径单测 | ✅ |
| V9.12 | Skill 市场：`install` from vendor + `scanner` 启发式 | install/scan CLI | ✅ |
| V9.13 | Console v2：任务/技能/连接器/Harbor Tab + API | `/api/*` + UI | ✅ |
| V9.14 | Harbor：harness-mount 探测 + 可选单题评分入口 | CLI dry 可跳过 | ✅ |
| V9.15 | 审计挂钩：Task 创建自动写 AuditLog + hooks | 自动落盘 | ✅ |
| V9.16 | `verify_v9.py` + ROADMAP/DELIVERABLE 更新 + commit | VERIFY V9 OK | ✅ |

## 明确不进 V9（产品边界）

- 腾讯 Electron / QClaw / 小程序 / 移动端壳
- 腾讯云托管、积分、账单、发票
- 腾讯文档 / IMA / 乐享专有 API（用本地 KB 等价）
- CDN 全站镜像
- 修改 Octop 核心 Dashboard React 路由（继续 Console 独立面）

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v9.py
# → VERIFY V9 OK
```
