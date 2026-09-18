# 通道入站（消息 → 任务）

配套：[`ACCEPTANCE_PACK.md`](./ACCEPTANCE_PACK.md)

**原则**：只做合同点名的通道；未点名不做全量 IM。  
本页描述 **入站**：一条消息创建一个 Console 任务。出站仍走环境变量 Webhook（见通道向导）。

## 1. API

```http
POST /api/channels/inbound
Authorization: Bearer <JWT>
Content-Type: application/json

{
  "channel": "feishu",
  "text": "帮我写周报",
  "sender": "ou_xxx",
  "chat_id": "oc_xxx",
  "project_id": "optional_project",
  "run": false,
  "dry": true
}
```

| 字段 | 说明 |
|---|---|
| `channel` | `feishu` / `dingtalk` / `wecom`（及别名 lark/ding/wxwork） |
| `text` | 消息正文（亦可塞飞书/钉钉/企微原始 webhook 体，由服务端抽取） |
| `run` | `true` 时建任务后立即执行 |
| `dry` | 与 `run` 联用；默认 `true` 演练 |

响应含 `task_id`；随后可在壳内打开该任务。

## 2. 合同勾选

| 通道 | 环境变量（出站，可选） | 入站验通命令 |
|---|---|---|
| 飞书 | `WB_FEISHU_WEBHOOK` / App 凭据 | `channel=feishu` |
| 钉钉 | `WB_DINGTALK_WEBHOOK` | `channel=dingtalk` |
| 企微 | `WB_WECOM_WEBHOOK` | `channel=wecom` |

网关侧（客户 IT）：将 IM 机器人回调转到贵司反向代理 → 本 API（需带租户 JWT 或由网关换发）。  
本仓库不托管各厂商长期 webhook 签名校验细节；生产网关应校验签名后再转发规范化 JSON。

## 3. 最小验通

```powershell
# 先 login 拿到 $token
curl -fsS -H "Authorization: Bearer $token" -H "Content-Type: application/json" `
  -d '{"channel":"feishu","text":"通道验收：写一个 hello.md","run":false}' `
  http://127.0.0.1:8010/api/channels/inbound
```

进程内单测覆盖：`scripts/verify_customer_playbook.py`。

## 4. 明确不做

- 未签约通道的适配
- 全量会话同步 / 已读回执 / 群管理
- 在无网关校验的情况下对公网裸奔 webhook
