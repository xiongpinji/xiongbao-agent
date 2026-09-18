# TASKBOARD — V16 四子集 Harbor + Casdoor/TLS 固化

> Smoke 已完成；Full 已后台启动。

## Done

1. 四子集 smoke **all_ok**（office/code/web/sec）  
2. Casdoor 生产清单 + GO_LIVE SSO 勾选  
3. Caddy `tls internal`；`https://localhost/api/health` 200  
4. Windows MAX_PATH / web judge 修复；full 长跑已启动（`--full`）

| ID | 状态 |
|---|---|
| V16.1 四子集 smoke live | ✅ |
| V16.2 四子集 full 启动 | ✅（后台） |
| V16.3 Casdoor/TLS 固化文档 | ✅ |
| V16.4 verify/docs/commit | 🟡 |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
$env:WB_BENCH_ROOT = 'W:\'
$env:WB_STAGE_ROOT = 'C:\wbstage'
$env:AUTO_BUILD_HARNESS_MOUNT = '1'
python -S scripts\run_harbor_four_subsets.py
```

## 距主线

- Full 四子集（260 tasks）耗时长，结果写入 `artifacts/harbor/four_subsets_full.json`  
- 公网 DNS 证书仍非门禁（本地 `tls internal` 已够私有化）
