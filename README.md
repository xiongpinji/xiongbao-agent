# xiongbao-agent — Octop × WorkBuddy V1

可商用的自托管多 Agent 工作台：**TencentCloud/Octop** + WorkBuddy 专家库 / Team 运行时。

| 项 | 说明 |
|---|---|
| 上游运行时 | [TencentCloud/Octop](https://github.com/TencentCloud/Octop) v1.0.0（MIT） |
| 专家来源 | `vendor/workbuddy-experts` + `vendor/workbuddyskills` |
| 评测框架 | `vendor/workbuddy-bench`（官方 Harbor 框架；题库需另下） |
| 本仓库远程 | https://github.com/xiongpinji/xiongbao-agent.git |

## V1 交付范围

已完成：

1. **wb2octop 转换器** — 246 专家 → Octop `experts/library/`（245 OK / 1 skip）
2. **Team 运行时** — Supervisor（lead + members），33 个 team 可 materialize
3. **投研 Demo** — `StockPartnerTeam` / `TradingAgentTeam` mock 跑通
4. **Smoke Bench 50 题** — 33 team + 17 agent，结构化 JSONL 指标
5. **验收脚本** — `scripts/verify_v1.py`

延后到 V2：Teach 录制 / Routine 引擎（原计划阶段 3）。  
延后到企业版：Casdoor RBAC / Milvus / systemd（原计划阶段 5 重型部分）。

## 目录要点

```
octop/
  contrib/workbuddy/          # wb2octop + team + bench
  src/octop/.../library/      # 转换后的专家包
vendor/
  workbuddy-experts/
  workbuddyskills/
  workbuddy-bench/            # 官方评测框架（浅克隆）
  RongXinAI/
tests/contrib/workbuddy/
scripts/verify_v1.py
artifacts/bench/              # 评测输出（gitignore）
```

## 快速验证（Windows / 无 pytest）

```powershell
cd "D:\AI编程库\项目库\进行中的项目\xiongbao agent"
python -S scripts\verify_v1.py
```

等价分步：

```powershell
python -S tests\contrib\workbuddy\run_tests.py
python -S tests\contrib\workbuddy\test_team_runtime.py
python -S tests\contrib\workbuddy\test_bench.py
python -S -m octop.contrib.workbuddy.bench.cli --sample 50 --out-dir artifacts\bench
python -S tests\contrib\workbuddy\demo_stock_partner.py
```

通过标准：单元测试全绿；smoke-50 **pass rate ≥ 90%**。

## 转换专家（如需重跑）

```powershell
python -S -m octop.contrib.workbuddy.cli --vendor vendor --output octop\src\octop\infra\agents\experts\library
```

## 官方 workbuddy-bench（可选）

HF 可访问时拉取 Office 50 题（约 10MB）：

```bash
# Git Bash / WSL
cd vendor/workbuddy-bench
./scripts/dataset/fetch-dataset.sh office
```

本仓库的 smoke bench **不依赖** HF；官方题需 Docker + Harbor 才能真正打分。  
数据集就位后可：

```powershell
python -S -m octop.contrib.workbuddy.bench.cli --list-office --dry-sample-only
```

## 环境要求

- Python **3.11+**（Octop 上游标 3.12+；本桥接层用 `python -S` 可在 3.11 跑通）
- 完整跑 Octop 服务：按 `octop/AGENTS.md`（uv、Node 等）
- 可选：Docker（官方 bench）

## License

- Octop / 本桥接代码：MIT
- WorkBuddy 专家资产：见 `vendor/` 各仓库 NOTICE（MIT / 原作者声明）
- workbuddy-bench：腾讯评测许可，见该仓库 LICENSE
