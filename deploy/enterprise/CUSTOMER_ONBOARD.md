# 真实客户开户与异地备份（无域名）

配套：[`ACCEPTANCE_PACK.md`](./ACCEPTANCE_PACK.md)（**签字总入口**） · [`GO_LIVE_CHECKLIST.md`](./GO_LIVE_CHECKLIST.md) · [`MULTI_TENANT.md`](./MULTI_TENANT.md) · [`RELIABILITY.md`](./RELIABILITY.md)

开户前先跑：

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_customer_playbook.py
```

## 1. 正式租户开户

本轮 go-live 演练户：`customer_a` / `customer_b`（admin key 在本机 `artifacts/secrets/go_live_tenant_keys.json`，**勿提交 git**）。

生产客户请用正式 ID（仅小写字母数字下划线）：

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:WB_ARTIFACTS_ROOT = Join-Path (Get-Location) 'artifacts'

python -S -m octop.contrib.workbuddy.tenant_cli create acme_corp --name "客户正式名A"
python -S -m octop.contrib.workbuddy.tenant_cli create globex_ltd --name "客户正式名B"
# 立刻把输出的 admin_api_key 写入离线密码库；只显示一次
```

入口（任选，不要求公网域名）：

- 容器内：`http://127.0.0.1:8010`
- 本机网关：`http://localhost`（Caddy）
- 内网：`http://<主机IP>`

Console 登录：租户 ID + `admin` + `admin_api_key` → JWT。

## 2. 异地备份约定

| 位置 | 用途 |
|---|---|
| `artifacts/backups/<tid>_golive.zip` | 本机热备份 |
| `D:\AI编程库\备份库\xiongbao-workbuddy\` | 本机第二路径（演练异地；生产请换成 NAS/对象存储） |

```powershell
python -S -m octop.contrib.workbuddy.tenant_cli backup <tid> --out artifacts\backups\<tid>.zip
Copy-Item artifacts\backups\<tid>.zip D:\AI编程库\备份库\xiongbao-workbuddy\
```

回滚：停 `wb-console-prod` → `tenant_cli restore <zip> --overwrite` → 验 `/api/tasks` → 再 start。

## 3. SSO / Milvus（本地可一键试）

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile casdoor --profile milvus up -d
```

`.env.workbuddy` 示例：

```
OCTOP_CASDOOR_ENDPOINT=http://host.docker.internal:8001
OCTOP_CASDOOR_CLIENT_ID=wb-local
OCTOP_CASDOOR_CLIENT_SECRET=wb-local-secret
OCTOP_MILVUS_URI=http://host.docker.internal:9091
```

Casdoor 需 MySQL（compose 已含 `casdoor-db` + `deploy/casdoor/app.conf`）。  
探测：`GET /api/enterprise` → `configured` / `reachable`。

换发：`POST /api/auth/login` body `{"casdoor_token":"..."}`（claims 需含 `tid`/`uid`）。  
向量集合：`tenant_cli milvus-ns <tid>` → `wb_<tid>`。

## 4. LLM（本机 Ollama）

已写入本机 `deploy/.env.workbuddy`（gitignore）：

```
WB_LLM_BASE_URL=http://host.docker.internal:11434/v1
WB_LLM_MODEL=qwen2.5:3b
```

宿主机需 `ollama serve` 且已 pull 模型。改后：

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod up -d wb-console-prod --force-recreate
```
