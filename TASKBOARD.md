# TASKBOARD — V15 OIDC 换发 / pptx / Harbor live

> 已完成。

## Done

1. Casdoor 应用 `wb-local` + 用户 `alice`（tag/affiliation/properties → `acme_corp`）  
2. Password grant → RS256 JWKS（stdlib）→ `exchange_casdoor_token` → Console `/api/auth/login` 换发 WB JWT  
3. pptx 文本预览（docx/xlsx/pptx）  
4. Harbor live=`local-openai-cbc-office-smoke` **ok=true rc=0**（~121s；含 harness mount 自动构建 + PATH 修复）  
5. `verify_v15.py` OK；Hub/health v=15

| ID | 状态 |
|---|---|
| V15.1 Casdoor claims + OIDC 换发联调 | ✅ |
| V15.2 pptx 预览 | ✅ |
| V15.3 Harbor live=1 评分 | ✅ |
| V15.4 verify/docs/commit | ✅ |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:OCTOP_CASDOOR_ENDPOINT = 'http://127.0.0.1:8001'
$env:OCTOP_CASDOOR_CLIENT_ID = 'wb-local'
$env:OCTOP_CASDOOR_CLIENT_SECRET = 'wb-local-secret'
python -S scripts\setup_casdoor_oidc.py
python -S scripts\verify_v15.py
# Harbor live（需 Docker + WB_LLM_* + bench .venv）
$env:AUTO_BUILD_HARNESS_MOUNT = '1'
python -S -c "from octop.contrib.workbuddy.bench.harbor import harbor_score_entry; print(harbor_score_entry(dry_run=False, timeout=3600)['ok'])"
```

## 距主线

- 公网域名 / 正式 TLS 证书（本地 Caddy 已通，**非交付门禁**）  
- Electron / 腾讯 SaaS / 小程序 — **明确非目标**  
- Harbor 全量四子集长跑（本次已通 office smoke 1 task；全量可另排）
