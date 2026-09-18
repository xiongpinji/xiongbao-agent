# 多租户上线检查单（Go-Live）

> 适用：`deploy/docker-compose.workbuddy.yml --profile prod`  
> 配套：[`MULTI_TENANT.md`](./MULTI_TENANT.md)  
> 验收脚本：`python -S scripts/verify_v11.py`

在每一项完成后打勾。**任一项 P0 未过，不得对客户开放。**

---

## 0. 发布基线（P0）

- [ ] 代码已在 `main`：`git log -1` 含 `feat(v11)` / Hub `v>=11`
- [ ] 本机/构建机：`PYTHONPATH=. python -S scripts/verify_v11.py` → `VERIFY V11 OK`
- [ ] 未把 `.env.workbuddy`、api_key、`WB_CONSOLE_SECRET` 提交进 git
- [ ] 域名 DNS 已指向本机公网 IP（或内网入口已就绪）

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
| `WB_DOMAIN` | 真实域名（Caddy TLS） | [ ] |
| `WB_LLM_*` | 生产可用模型端点 | [ ] |
| `OCTOP_CASDOOR_*` | 若用企业 SSO 则全部填齐 | [ ] |
| `OCTOP_MILVUS_URI` | 若用向量库则填齐 | [ ] |

---

## 2. 启动生产栈（P0）

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod config
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy --profile prod up -d
docker compose -f deploy/docker-compose.workbuddy.yml stop wb-console
```

- [ ] `config` 无报错（尤其 `WB_CONSOLE_SECRET` 已设置）
- [ ] `wb-console-prod` / `caddy` / `octop` / `tick` 为 `running` 或 healthy
- [ ] 宿主机 **未** 对外映射 `8010`（已 `stop wb-console`）
- [ ] `https://$WB_DOMAIN/api/health` 返回 `{"ok":true,"auth_required":true,...}`
- [ ] 宿主机 `artifacts/` 与容器 `/app/artifacts` 为同一绑定（Compose 已用 `../artifacts:/app/artifacts`，便于 CLI 开户）

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --profile prod ps
curl -fsS "https://$env:WB_DOMAIN/api/health"
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
curl -s -o NUL -w "%{http_code}" -H "Authorization: Bearer bad" "https://$env:WB_DOMAIN/api/tasks"
# 期望 401

$tokenA = ... # login 输出
curl -fsS -H "Authorization: Bearer $tokenA" "https://$env:WB_DOMAIN/api/tenant"
curl -fsS -H "Authorization: Bearer $tokenA" "https://$env:WB_DOMAIN/api/tasks"
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

- [ ] 防火墙仅放行 80/443（及运维 SSH）
- [ ] `WB_CONSOLE_SECRET` 已轮换且与文档中的临时值不同
- [ ] `artifacts/tenants` 权限仅服务账号可读（Linux 建议 `0700`）
- [ ] 日志不含明文 api_key / JWT
- [ ] 管理员名单与租户 `admin` 角色已登记

---

## 7. 客户交付签字

| 项 | 客户A | 客户B |
|---|---|---|
| 租户 ID | | |
| 管理员账号 | | |
| 入口 URL | | |
| 隔离抽检通过 | [ ] | [ ] |
| 备份策略已知晓 | [ ] | [ ] |

**放行人**：__________ **日期**：__________

---

## 常见故障

| 现象 | 处理 |
|---|---|
| compose 报 `WB_CONSOLE_SECRET` | 在 `.env.workbuddy` 设置后再 `--profile prod up` |
| `:8010` 仍公网可达 | `stop wb-console`；确认未另开开发 compose |
| Caddy 证书失败 | 查 DNS / 80 可达；内网可用 `tls internal` 改 Caddyfile |
| 401 但密钥正确 | 查 `WB_CONSOLE_SECRET` 是否与签发时一致；时钟偏差 |
| 两租户能看见同一 tasks | 确认登录 JWT 的 `tid`；确认 `WB_ARTIFACTS_ROOT` 指向同一卷 |
