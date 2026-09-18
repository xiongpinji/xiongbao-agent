# 多租户上线检查单（Go-Live）

> 适用：`deploy/docker-compose.workbuddy.yml --profile prod`  
> 配套：[`MULTI_TENANT.md`](./MULTI_TENANT.md)  
> 验收脚本：`python -S scripts/verify_v11.py`

**交付标准（P0）= 多租户隔离 + Console 鉴权 + 可私有化启动。**  
域名 / 公网 DNS / 公网证书 **不是** 交付门槛（属可选运维增强）。

在每一项完成后打勾。**任一项 P0 未过，不得对客户开放。**

---

## 0. 发布基线（P0）

- [ ] 代码已在 `main`：`git log -1` 含 `feat(v11)` / Hub `v>=11`
- [ ] 本机/构建机：`PYTHONPATH=. python -S scripts/verify_v11.py` → `VERIFY V11 OK`
- [ ] 未把 `.env.workbuddy`、api_key、`WB_CONSOLE_SECRET` 提交进 git
- [ ] 访问入口已明确（内网 IP / 主机名 / 反代均可；**不要求**公网域名）

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v11.py
git log -1 --oneline
```

---

## 1. 密钥与环境（P0）

复制并编辑（**勿入库**）：

```powershell
Copy-Item deploy\.env.workbuddy.example deploy\.env.workbuddy
```

| 变量 | 要求 | 完成 |
|---|---|---|
| `WB_CONSOLE_SECRET` | `openssl rand -hex 32` 或等效强随机 | [ ] |
| `WB_MULTI_TENANT` | `1` | [ ] |
| `WB_CONSOLE_AUTH` | `1` | [ ] |
| `WB_LLM_*` | 生产可用模型端点（若本阶段就要跑 live） | [ ] |
| `WB_DOMAIN` | **可选**；仅在启用 Caddy 公网/内网主机名 TLS 时填写，默认 `localhost` 即可 | [ ] |
| `OCTOP_CASDOOR_*` | **可选**：企业 SSO | [ ] |
| `OCTOP_MILVUS_URI` | **可选**：向量库 | [ ] |

---

## 2. 启动生产栈（P0）

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod config
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod up -d
docker compose -f deploy/docker-compose.workbuddy.yml stop wb-console
```

- [ ] `config` 无报错（尤其 `WB_CONSOLE_SECRET` 已设置）
- [ ] `wb-console-prod`（及按需 `caddy` / `octop` / `tick`）为 `running` 或 healthy
- [ ] 宿主机 **未** 对外裸奔映射开发用 `8010`（已 `stop wb-console`）；或仅内网可达
- [ ] 健康检查通过（任选其一，**不绑定域名**）：
  - 容器内：`curl http://127.0.0.1:8010/api/health` → `auth_required: true`
  - 经网关：`https://localhost/api/health` 或 `http(s)://<内网IP>/api/health`
- [ ] 宿主机 `artifacts/` 与容器 `/app/artifacts` 为同一绑定

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --profile prod ps
docker exec deploy-wb-console-prod-1 python -S -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/api/health').read().decode())"
```

---

## 3. 开户与隔离验收（P0）

```powershell
$env:PYTHONPATH = (Get-Location).Path
# 建议在挂载了 artifacts 的容器或宿主机同一卷上执行
python -S -m octop.contrib.workbuddy.tenant_cli create acme --name "客户A"
python -S -m octop.contrib.workbuddy.tenant_cli create globex --name "客户B"
# 保存两侧 admin_api_key
```

| 检查 | 命令/预期 | 完成 |
|---|---|---|
| 登录 A | `tenant_cli login acme admin <key>` 得 JWT | [ ] |
| 无 token | `GET /api/tasks` → **401** | [ ] |
| A 建任务 | Bearer A → `POST /api/runtime/run-task` 或 CLI 写入 A 根 | [ ] |
| B 列表 | Bearer B → `/api/tasks` **不含** A 的 task | [ ] |
| 路径 | 仅存在 `artifacts/tenants/acme/...` 与 `globex/...` | [ ] |
| Milvus | `tenant_cli milvus-ns acme` → `wb_acme` | [ ] |

```powershell
# 入口可用容器内端口、内网 IP 或网关；不要求公网域名
curl -s -o NUL -w "%{http_code}" http://127.0.0.1:8010/api/tasks
# 期望 401（无 Authorization）

$tokenA = ... # login 输出
curl -fsS -H "Authorization: Bearer $tokenA" http://127.0.0.1:8010/api/tenant
curl -fsS -H "Authorization: Bearer $tokenA" http://127.0.0.1:8010/api/tasks
```

---

## 4. SSO / 向量库（P1，选用才做）

- [ ] Casdoor 可登录；`POST /api/auth/login` body `{"casdoor_token":"..."}` 换发成功
- [ ] Casdoor claims 含 `tid`/`tenant` 与 `uid`/`name`/`sub`
- [ ] Milvus 可达；不同 `WB_TENANT_ID` 写入不同 collection

---

## 5. 备份与回滚（P0）

```powershell
python -S -m octop.contrib.workbuddy.tenant_cli backup acme --out D:\backups\acme.zip
# 演练（ staging ）：restore --overwrite
```

- [ ] 每租户至少一份异地备份路径已约定
- [ ] 演练过一次 restore（可在 staging）
- [ ] 记录回滚：停流量 → restore 出问题户 → 验 `/api/tasks` → 再开流量

---

## 6. 安全加固（P0）

- [ ] 管理面与 Console **不**对未授权网络裸奔（内网 / VPN / 反代鉴权均可；不强制公网 443）
- [ ] `WB_CONSOLE_SECRET` 已轮换且与文档中的临时值不同
- [ ] `artifacts/tenants` 权限仅服务账号可读（Linux 建议 `0700`）
- [ ] 日志不含明文 api_key / JWT
- [ ] 管理员名单与租户 `admin` 角色已登记

---

## 7. 可选：域名与公网 TLS（非交付标准）

仅当需要对外主机名或自动公网证书时再做：

- [ ] 配置 `WB_DOMAIN` 与 DNS
- [ ] Caddy 签出证书；`https://<域名>/api/health` 可用

---

## 8. 客户交付签字

| 项 | 客户A | 客户B |
|---|---|---|
| 租户 ID | | |
| 管理员账号 | | |
| 入口 URL（IP/内网/域名均可） | | |
| 隔离抽检通过 | [ ] | [ ] |
| 备份策略已知晓 | [ ] | [ ] |

**放行人**：__________ **日期**：__________

---

## 常见故障

| 现象 | 处理 |
|---|---|
| compose 报 `WB_CONSOLE_SECRET` | 在 `.env.workbuddy` 设置后再 `--profile prod up` |
| `:8010` 仍对未授权网络可达 | `stop wb-console`；或加防火墙/VPN |
| Caddy 证书失败 | **可忽略域名**，直接用容器 `8010` 验收；需要主机名时用 `tls internal` 或修好 DNS |
| 401 但密钥正确 | 查 `WB_CONSOLE_SECRET` 是否与签发时一致；时钟偏差 |
| 两租户能看见同一 tasks | 确认登录 JWT 的 `tid`；确认 `WB_ARTIFACTS_ROOT` 指向同一卷 |
