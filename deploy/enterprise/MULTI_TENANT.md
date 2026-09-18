# 多租户生产部署 Runbook

本文说明如何把 xiongbao-agent（Octop + WorkBuddy）以**多租户**方式私有化部署。

## 架构

```
Internet
   │
   ▼
Caddy :443 (TLS)
   │
   ├─► wb-console-prod :8010   (JWT 鉴权，按 tid/uid 隔离 artifacts)
   └─► octop :8000             (可选 --profile prod/full；Octop 多用户)
```

数据布局：

```
artifacts/
  tenants/
    _registry.json              # 租户注册表
    <tenant_id>/
      _shared/                  # 租户共享
      users/<user_id>/
        tasks/
        knowledge/
        cowrite/
        library/
        security/
        models/
        china_im/
        skillhub/installed/
```

## 环境变量（生产必填）

| 变量 | 含义 |
|---|---|
| `WB_MULTI_TENANT=1` | 启用多租户语义 |
| `WB_CONSOLE_AUTH=1` | Console API 强制 Bearer |
| `WB_CONSOLE_SECRET` | JWT 签名密钥（强随机，勿用默认值） |
| `WB_ARTIFACTS_ROOT` | artifacts 根（Compose 内 `/app/artifacts`） |
| `WB_DOMAIN` | Caddy 域名（用于 TLS） |
| `OCTOP_CASDOOR_*` | 可选：企业 SSO，登录可换发 Console JWT |
| `OCTOP_MILVUS_URI` | 可选：向量库；collection 自动 `wb_<tid>` |

复制：`deploy/.env.workbuddy.example` → `deploy/.env.workbuddy`

## 一键启动（生产）

```bash
# 1. 填好密钥与域名
export WB_CONSOLE_SECRET="$(openssl rand -hex 32)"
export WB_DOMAIN=agent.example.com

# 2. 启动（Caddy + 鉴权 Console + Octop）
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod up -d
# 关闭开发用裸奔 :8010（默认 wb-console 仍会随 tick 拉起）
docker compose -f deploy/docker-compose.workbuddy.yml stop wb-console

# 3. 创建租户（在宿主机或 tick 容器内）
export PYTHONPATH=.
python -S -m octop.contrib.workbuddy.tenant_cli create acme --name "Acme Corp"
# → 保存返回的 admin_api_key

# 4. 登录拿 JWT
python -S -m octop.contrib.workbuddy.tenant_cli login acme admin '<admin_api_key>'

# 5. 调 Console（经 Caddy）
curl -H "Authorization: Bearer <token>" https://agent.example.com/api/tasks
```

## 隔离验收清单

1. 创建租户 `acme` 与 `globex`，各自 `admin` 登录。
2. A 创建 task，B 的 `/api/tasks` 不得出现该 task。
3. 无 token 访问 `/api/tasks` → **401**。
4. Milvus：`WB_TENANT_ID=acme` 时 collection 为 `wb_acme`。
5. `tenant_cli backup acme` / `restore` 不影响 `globex`。

## 权限建议

- `artifacts/tenants` 目录 `0700`，仅运行用户可读。
- 不要把 `WB_CONSOLE_SECRET`、api_key 写入镜像层或 git。
- 生产勿映射宿主机 `8010`（仅用 Caddy 443）。

## 与 Octop 多用户的关系

| 层 | 职责 |
|---|---|
| Octop `users` / JWT | 平台登录、agent 归属、Dashboard |
| WorkBuddy `tenants` | 产品面数据隔离（任务/KB/共写）与 Console 运维鉴权 |

映射建议：Octop `username` ↔ WorkBuddy `user_id`；组织名 ↔ `tenant_id`。Casdoor org 可作为 `tid` claim。

## 备份

```bash
python -S -m octop.contrib.workbuddy.tenant_cli backup acme --out /var/backups/acme.zip
python -S -m octop.contrib.workbuddy.tenant_cli restore /var/backups/acme.zip --overwrite
```

整实例备份仍可用 Octop `infra/backup`；租户切片用于客户迁出/DR。

## 验收脚本

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v11.py
```
