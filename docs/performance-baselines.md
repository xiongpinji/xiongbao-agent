# 性能基线（启动 / 内存 / IPC）

本目录汇总当前仓库内可复用的性能基准测试入口。所有脚本均为 CI-friendly：可重复、有预算门禁、不依赖网络。

## 仓库脚本清单

| 关注点 | 入口 | 衡量内容 |
| --- | --- | --- |
| Octop 后端冷启动 + HTTP 延迟 | `octop/scripts/perf_baseline.py` | 5 次 `OctopServer.start()` 中位数 + `/api/health` 内网 RTT |
| RongXinAI Renderer bundle 体积 | `vendor/RongXinAI/scripts/check-renderer-bundle-budget.cjs` | preload / startup 图与单 chunk 上限 |
| RongXinAI 内存泄漏 | `vendor/RongXinAI/scripts/ci/memory-leak-check.mjs` | Electron 主进程 + Renderer 堆 20 轮周期采样 |
| RongXinAI 启动画像 | `vendor/RongXinAI/src/main/startupProfiler.ts` | 主进程阶段用时埋点 |
| Console 首屏 / DOM 烟雾 | `octop/contrib/workbuddy/console/e2e/run-smoke.mjs` | Playwright Chromium 三页加载时间 |

## 运行

### Octop 后端

```bash
cd octop
uv run python scripts/perf_baseline.py
```

预期（首批基线）：
```
[perf] server-startup: median=1194ms p95=1204ms budget=8000ms -> PASS
[perf] http-latency:   median=3ms    p95=3ms    budget=250ms  -> PASS
```

越界即退出码 1。

### RongXinAI Renderer

```bash
cd vendor/RongXinAI
npm run test:bundle-budget          # bundle 体积门禁
npm run test:memory-leak            # Electron 内存周期采样（CI nightly）
```

`startupProfiler` 默认随应用启动；其结果写入用户数据目录下的日志，可在调试时读取。

### Console Web

```bash
node octop/contrib/workbuddy/console/e2e/run-smoke.mjs
```

脚本会打印三页各自的加载耗时，作为浏览器侧首屏基线。

## 门禁策略

- `perf_baseline.py` 的预算可在脚本顶部 `STARTUP_BUDGET_S` / `HTTP_LATENCY_BUDGET_S` 收紧；
  当前为「首次落地」宽限值，待 CI 跑出真实分布后再调。
- `check-renderer-bundle-budget.cjs` 的预算来自 PR #141 的当前状态，目标值见脚本注释
  （startup ≤ 2.0 MiB raw / 700 KiB gzip）。
- `memory-leak-check.mjs` 已经在 GitHub Actions 的 `memory-leak-nightly.yml` 中
  每夜运行；本地可手动触发以验证修复。

## 添加新基线

1. 在对应的子目录添加独立脚本，遵循 "5 次采样取中位 + 固定预算" 的模式。
2. 在本表新增一行入口。
3. 接入对应项目的 CI workflow（Octop: `.github/workflows/*.yml`；RongXinAI:
   `vendor/RongXinAI/.github/workflows/*.yml`），至少在 push / nightly 中跑一次。
