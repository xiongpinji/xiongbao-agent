# Casdoor 生产接线清单（V16）

本地联调已用 `scripts/setup_casdoor_oidc.py` 跑通。上正式环境按本清单替换密钥与组织，**不要**把 client secret 提交进 git。

## 1. Compose

```powershell
docker compose -f deploy/docker-compose.workbuddy.yml --env-file deploy/.env.workbuddy `
  --profile prod --profile casdoor --profile milvus up -d
```

环境变量（写入 `deploy/.env.workbuddy`，已 gitignore）：

| 变量 | 说明 |
|---|---|
| `OCTOP_CASDOOR_ENDPOINT` | 对 Console 容器可达的 URL（例 `http://casdoor:8000` 或 `http://host.docker.internal:8001`） |
| `OCTOP_CASDOOR_CLIENT_ID` | 正式应用 client id |
| `OCTOP_CASDOOR_CLIENT_SECRET` | 正式应用 secret |
| `WB_CONSOLE_AUTH=1` | 强制 JWT |
| `WB_CONSOLE_SECRET` | WB JWT 签名密钥（与 Casdoor 无关，强随机） |

## 2. Casdoor 控制台必配

1. **Application**：启用 Password + Authorization Code；`tokenFormat=JWT`；`grantTypes` 含 `password` / `authorization_code` / `refresh_token`
2. **Cert**：使用正式证书（RS256 / JWKS）；Console 通过 `/.well-known/jwks` 校验
3. **User claims**（任一即可映射 `tid`）：
   - `tag` = 租户 id  
   - 或 `affiliation` = 租户 id  
   - 或 `properties.tid` / `properties.tenant`
4. **User**：`name` → `uid`；`properties.role` → `admin|user`
5. 密码必须用 **Set Password** API/UI；`update-user` 不会改密码

## 3. 换发验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:OCTOP_CASDOOR_ENDPOINT = 'https://sso.example.com'   # 正式
$env:OCTOP_CASDOOR_CLIENT_ID = '<prod-client-id>'
$env:OCTOP_CASDOOR_CLIENT_SECRET = '<prod-secret>'
$env:WB_OIDC_USER = '<real-user>'
$env:WB_OIDC_PASSWORD = '<real-password>'
$env:WB_OIDC_TENANT = '<tenant_id>'
python -S scripts\setup_casdoor_oidc.py
```

期望：`verified=true alg=RS256`，`exchange.tid` 正确，Console `casdoor_token` 登录返回 WB JWT。

## 4. 安全

- 生产禁用默认 `admin/123`
- client secret 仅存 env / 密钥管理，不进镜像层
- Console 不对外裸奔 8010；走 Caddy（`tls internal` 或公网证书）
