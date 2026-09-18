# 客户交付验收包（可勾选）

> **定位**：签约前 / 上线当天的唯一勾选入口。  
> **配套**：[`GO_LIVE_CHECKLIST.md`](./GO_LIVE_CHECKLIST.md) · [`CUSTOMER_ONBOARD.md`](./CUSTOMER_ONBOARD.md) · [`RELIABILITY.md`](./RELIABILITY.md) · [`CHANNEL_INBOUND.md`](./CHANNEL_INBOUND.md)

**一键门禁（开发机 / CI）**：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_delivery_pack.py
```

期望末行：`VERIFY DELIVERY PACK OK`

**客户剧本（进程内，不依赖已起的 console）**：

```powershell
python -S scripts\verify_customer_playbook.py
```

**现场对活 console（可选）**：

```powershell
$env:WB_PLAYBOOK_BASE = "http://127.0.0.1:8010"
$env:WB_PLAYBOOK_TID = "<租户ID>"
$env:WB_PLAYBOOK_UID = "admin"
$env:WB_PLAYBOOK_KEY = "<admin_api_key>"
python -S scripts\verify_customer_playbook.py --live
```

---

## A. 客户剧本（P0 — 任一项不过不得签字）

剧本：`登录 → 建项目 → 挂技能 → 真执行 → 产物下载 → 成员权限`

| # | 步骤 | 预期 | 勾选 |
|---|---|---|---|
| A1 | 租户登录签发 JWT | `POST /api/auth/login` 成功 | [ ] |
| A2 | 创建项目，owner=管理员 | `POST /api/projects` | [ ] |
| A3 | 安装技能并「存入项目」 | `skills/deposit` 成功；项目 skill 列表可见 | [ ] |
| A4 | 归属项目的任务真执行 | 状态 `completed`；workspace 有产物 | [ ] |
| A5 | 产物可下载/预览 | `download` / 右侧预览可用 | [ ] |
| A6 | 成员角色 | viewer 无法存技能；editor/owner 可以 | [ ] |
| A7 | 剧本脚本绿 | `verify_customer_playbook.py` → OK | [ ] |

---

## B. 上线基础设施（P0）

完整项见 [`GO_LIVE_CHECKLIST.md`](./GO_LIVE_CHECKLIST.md)。此处只摘要：

| # | 项 | 勾选 |
|---|---|---|
| B1 | `WB_CONSOLE_SECRET` / 多租户 / 鉴权已开 | [ ] |
| B2 | `wb-console-prod` healthy；`/api/health` ok | [ ] |
| B3 | 两租户隔离抽检通过 | [ ] |
| B4 | 备份 + 一次 restore 演练 | [ ] |
| B5 | 密钥未入库 | [ ] |

---

## C. 可靠性与观测（P0）

见 [`RELIABILITY.md`](./RELIABILITY.md)。

| # | 项 | 勾选 |
|---|---|---|
| C1 | `GET /api/ops` 返回 uptime / restart_hint | [ ] |
| C2 | 失败任务 `GET /api/tasks/{id}/replay` 可看事件+错误 | [ ] |
| C3 | 配额超限创建任务返回 429 | [ ] |
| C4 | 运维已知重启预案命令 | [ ] |

---

## D. 通道实连（P1 — 合同点名才做）

见 [`CHANNEL_INBOUND.md`](./CHANNEL_INBOUND.md)。

| 通道 | 合同要求 | 入站验通 | 勾选 |
|---|---|---|---|
| 飞书 | [ ] 要 / [ ] 不要 | `POST /api/channels/inbound` channel=feishu | [ ] |
| 钉钉 | [ ] 要 / [ ] 不要 | channel=dingtalk | [ ] |
| 企微 | [ ] 要 / [ ] 不要 | channel=wecom | [ ] |

未点名的通道：**不做**。

---

## E. 客户上手（签字前交给客户）

| # | 交付物 | 勾选 |
|---|---|---|
| E1 | 入口 URL（内网 IP / 网关均可） | [ ] |
| E2 | 租户 ID + admin 账号（密钥离线交付） | [ ] |
| E3 | 本验收包勾选副本（可附 `artifacts/go_live/SIGN_OFF.md`） | [ ] |
| E4 | 开户步骤已按 [`CUSTOMER_ONBOARD.md`](./CUSTOMER_ONBOARD.md) 执行 | [ ] |

**放行人**：__________ **日期**：__________ **基线 commit**：__________
