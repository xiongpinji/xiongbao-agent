# TASKBOARD — WorkBuddy 运行时贯通（V10）

> 基线：V1–V9 已交付（产品面对齐）。  
> 本板覆盖：**把 V9 孤岛能力串成可执行闭环**（Task 跑通、策略生效、入站轮询、Skill 入目录、KB/档案注入、打包导出）。  
> **边界不变**：不复刻 Electron/QClaw、腾讯云 SaaS、小程序/计费、腾讯文档专有 API。

## V9（已完成，归档）

| ID | 交付物 | 状态 |
|---|---|---|
| V9.1–V9.16 | 任务 / 权限 / 数据 / 模型 / worktree / 微信QQ / 资料库 / 灵感 / KB / 共写 / 通道桥 / Skill / Console / Harbor / 审计 / verify | ✅ |

## V10 任务拆解（一次性）

| ID | 交付物 | 验收 | 状态 |
|---|---|---|---|
| V10.1 | `runtime/task_runner`：Task → GoalEngine 执行（dry/live） | 单测 dry 路径 | ✅ |
| V10.2 | `runtime/policy_gate`：跑 Task/Goal 前校验 SecurityPolicy | ask 拒写 / craft 放行 | ✅ |
| V10.3 | `runtime/profile_env`：激活 ModelProfile → env/caller | 注入 base_url/model | ✅ |
| V10.4 | `runtime/inbox_poll`：Inbox JSONL → ChannelBridge | 游标不重复消费 | ✅ |
| V10.5 | `runtime/skill_register`：install + 写入 installed 索引 | 目录可被 Catalog 扫到 | ✅ |
| V10.6 | `runtime/kb_context`：KB search 注入记忆上下文 | 命中片段进 prompt 前缀 | ✅ |
| V10.7 | `runtime/bundle_export`：多根（tasks/kb/cowrite/…）打包 | zip 往返 | ✅ |
| V10.8 | Task create 可选 git worktree 绑定 | meta.worktree 落盘 | ✅ |
| V10.9 | Cowrite export → LibraryIndex 发布 | library list 可见 | ✅ |
| V10.10 | Console `/api/runtime/*` + Hub v10 + `verify_v10` + docs | VERIFY V10 OK | ✅ |

## 明确不进 V10

- Harbor **真机全量**评分（入口已有；本板只保 dry/harness）
- 腾讯闭源桌面壳 / 云托管 / 计费
- 修改 Octop 核心 Dashboard React

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v10.py
# → VERIFY V10 OK
```
