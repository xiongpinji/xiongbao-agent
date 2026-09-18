# 可靠性与观测（私有化交付）

配套：[`ACCEPTANCE_PACK.md`](./ACCEPTANCE_PACK.md)

## 1. 健康与运维快照

| 接口 | 用途 |
|---|---|
| `GET /api/health` | 公开健康（含 `uptime_s` / `restart_hint` / `v`） |
| `GET /api/ops` | 鉴权后运维快照 + 完整重启 playbook |

```powershell
curl -fsS http://127.0.0.1:8010/api/health
curl -fsS -H "Authorization: Bearer <JWT>" http://127.0.0.1:8010/api/ops
```

## 2. 任务失败回放

| 接口 | 用途 |
|---|---|
| `GET /api/tasks/{id}/replay` | 事件流 + 最近消息 + 错误摘要 |
| `GET /api/tasks/{id}/run-events` | 纯事件 JSON |
| 壳内「轨迹」页签 | 可视化回放 |

失败定位顺序：

1. 壳内打开任务 → 结果区「轨迹」
2. `replay` 看 `error` / `terminal`
3. `docker logs --tail 200 deploy-wb-console-prod-1`

## 3. 配额与租户隔离

- 创建任务时校验 `check_can_create_task`；超限 → **HTTP 429** + `code`
- 租户数据根：`artifacts/tenants/<tid>/...`
- 压测/验收：`python -S scripts/verify_customer_playbook.py`（含配额与隔离断言）

调整配额：

```powershell
python -S -m octop.contrib.workbuddy.tenant_cli quota <tid> --max-tasks 200
```

## 4. Console 重启预案

```powershell
# 1) 健康
curl -fsS http://127.0.0.1:8010/api/health

# 2) 日志
docker logs --tail 200 deploy-wb-console-prod-1

# 3) 重建（保留 artifacts 卷）
docker compose -f deploy/docker-compose.workbuddy.yml `
  --env-file deploy/.env.workbuddy --profile prod `
  up -d wb-console-prod --force-recreate

# 4) 复验剧本
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_customer_playbook.py
```

回滚租户数据：见 [`CUSTOMER_ONBOARD.md`](./CUSTOMER_ONBOARD.md) 备份/restore。

## 5. 日志纪律

- 勿在日志打印 api_key / JWT 全文
- 密钥仅存 `artifacts/secrets/`（gitignore）
- 客户问题单附：`task_id` + `replay` JSON + 容器日志尾部
