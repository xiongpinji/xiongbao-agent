# V8 任务板：生产化路径（Harbor → Compose → Console）

目标：把 V7 能力对齐结果落到**可常驻运行**的路径，不做 Electron/QClaw 复刻。

| ID | 项 | 验收 | 状态 |
|----|----|------|------|
| V8.1 | `uv sync --python 3.12` 于 `vendor/workbuddy-bench` | `.venv` 存在且 `python>=3.12` | ✅ |
| V8.2 | 官方 Harbor dry-run job（office first-1） | `scripts/dry_run_office_smoke.sh` 打印 Resolved Manifest | ✅ |
| V8.3 | Harbor 桥扩展：`sync` / `dry-run` / 探测 .venv | `harbor_cli status` 显示 `bench_synced=true` | ✅ |
| V8.4 | Compose 可真起：tick + console 默认；octop 走 profile | `docker compose config` + `up -d` | ✅ |
| V8.5 | WorkBuddy Console（静态 UI + 本地 JSON API） | `console_server` :8010 | ✅ |
| V8.6 | `hub_cli` 统一入口 | `status` 聚合 harbor/audit/enterprise | ✅ |
| V8.7 | 测试 + verify / commit | `test_v8_production` 绿 | ✅ |

非目标：CDN 全量镜像、腾讯 SaaS、改 Octop 核心 Dashboard 路由（Console 独立挂载，避免拖垮 `make all`）。

## 常用命令

```bash
# Harbor
cd vendor/workbuddy-bench && uv sync --python 3.12
# Windows: set PYTHON_BIN=...\.venv\Scripts\python.exe
bash scripts/dry_run_office_smoke.sh

# Hub / Console
python -m octop.contrib.workbuddy.hub_cli status
python -m octop.contrib.workbuddy.console_server --port 8010

# Compose
docker compose -f deploy/docker-compose.workbuddy.yml up -d
# 浏览器: http://127.0.0.1:8010/
```
