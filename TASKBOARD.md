# TASKBOARD — WorkBuddy 全量对齐

> 目标：**能力与腾讯 WorkBuddy 全量对齐**。  
> **边界**：闭源 Electron / 腾讯云 SaaS → Octop Dashboard + Docker Compose 等价。

## 基线 V1–V6

| 阶段 | 状态 |
|---|---|
| V1–V6 | ✅ |

## V7 — 全量对齐

| ID | 交付物 | 状态 |
|---|---|---|
| V7.1 | `templates/nunjucks_lite` + `--official-tpl` | ✅ |
| V7.2 | `bench/harbor.py` + `harbor_cli` | ✅ |
| V7.3 | sec 子集 60 题 | ✅ |
| V7.4 | Casdoor JWT + Milvus REST | ✅ |
| V7.5 | `project/space` + CLI | ✅ |
| V7.6 | `office/artifacts` + CLI | ✅ |
| V7.7 | email / webhook connectors | ✅ |
| V7.8 | `audit/` JSONL | ✅ |
| V7.9 | `deploy/docker-compose.workbuddy.yml` | ✅ |
| V7.10 | `scripts/fetch_cdn_snapshot.ps1` | ✅ |
| V7.11 | `scripts/verify_full.py` | ✅ |

## 验收

```powershell
python -S scripts\verify_full.py
```
