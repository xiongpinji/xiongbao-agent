# xiongbao-agent — Octop × WorkBuddy

可商用的自托管多 Agent 工作台：**TencentCloud/Octop** + WorkBuddy 专家库 / Team / Teach·Routine。

| 项 | 说明 |
|---|---|
| 上游运行时 | [TencentCloud/Octop](https://github.com/TencentCloud/Octop) v1.0.0（MIT） |
| 专家来源 | `vendor/workbuddy-experts` + `vendor/workbuddyskills` |
| 评测框架 | `vendor/workbuddy-bench`（官方 Harbor 框架；题库需另下） |
| 本仓库远程 | https://github.com/xiongpinji/xiongbao-agent.git |

## 运维 / 升级 / 回滚

- 集成手册：[docs/INTEGRATION.md](docs/INTEGRATION.md)
- **端到端交付指南：[docs/DELIVERY_GUIDE.md](docs/DELIVERY_GUIDE.md)**
- 性能基线：[docs/performance-baselines.md](docs/performance-baselines.md)
- a11y 报告：[docs/a11y-report.md](docs/a11y-report.md)
- 安全审计：[docs/security-audit.md](docs/security-audit.md)
- 数据迁移回滚：[docs/rollback.md](docs/rollback.md)

## 交付范围

**V1（已完成）**

1. **wb2octop 转换器** — 246 专家 → Octop `experts/library/`（245 OK / 1 skip）
2. **Team 运行时** — Supervisor（lead + members），33 个 team 可 materialize
3. **投研 Demo** — `StockPartnerTeam` / `TradingAgentTeam` mock 跑通
4. **Smoke Bench 50 题** — 33 team + 17 agent，结构化 JSONL 指标
5. **本地 LLM** — Ollama OpenAI 兼容调用 + profile→模型匹配下载
6. **验收脚本** — `scripts/verify_v1.py`

**V2（已完成 MVP）**

1. **Teach recorder** — 录制 navigate/read/decision/message 步骤
2. **SkillDraft** — 从录音生成草稿，人工 `approve` 后才能建 Routine
3. **Routine 引擎** — dry / test / live；安全闸门与 bot 上限；run 持久化
4. **CLI + 单测** — `teach_cli` + `test_teach_routine.py`
5. **Scheduler** — stdlib 5 字段 cron + `due`/`tick`（系统计划任务驱动）
6. **LLM drafter** — 规则草稿 + 本地模型润色（`--llm`），人工 approve 仍强制
7. **CDP 录制 + UI 回放** — `cdp-record` / `--cdp-replay`（Chrome 9222）
8. **Connectors** — Notion 读页、飞书 webhook + 开放平台 `im/v1/messages`（`--outbound` + 环境变量门禁）

**V3（已完成 MVP）**

1. **Goal / Craft** — 自然语言目标 → 规划 → 执行 → 逐条验收 → 失败重试
2. **CLI** — `goal_cli demo|plan|run|list`（`--llm` 可选润色）
3. **SkillHub 运行时绑定** — 扫描 `vendor/workbuddyskills/skills`，enable/compose/prompt pack；Team `live_cli --skill` 注入

**V4（商用硬化）**

1. **SkillHub 白名单脚本沙箱** — `skills_cli scripts|exec`，仅 `scripts/` 内相对路径
2. **Goal ← SkillHub** — `goal_cli --skill` 注入 compose 上下文
3. **Outbox 投递日志与重试** — `outbox/delivery.jsonl` + `teach_cli retry-outbox`
4. **验收** — `scripts/verify_v4.py`

**V5（Office + 企业包装文档）**

1. **Office 题库** — `scripts/fetch_office_dataset.ps1`（HF → gitignored datasets）
2. **llm_lite 评分** — 无 Docker；本地 LLM + 启发式/可选 judge（`--office --live-llm`）
3. **systemd + Casdoor/Milvus 文档门禁** — `deploy/systemd/`、`deploy/enterprise/README.md`
4. **验收** — `scripts/verify_v5.py`

**V6（WorkBuddy 工作流补齐）**

1. **Ask / Plan / Craft** — `modes/` 装配器；Team `live_cli --mode`；Goal `--work-mode`
2. **工作区记忆** — SOUL/USER/MEMORY/daily 注入
3. **连接器扩展** — 钉钉/企微 webhook + 103 包 `connectors_cli`
4. **专家路由** — `router_cli route`
5. **Bench 全子集** — `fetch_bench_subsets.ps1` + `--list-subsets`
6. **builtin SkillHub** — skill-creator 等
7. **企业软探测** — `enterprise_cli probe`
8. **一键验收** — `scripts/verify_all.py`

**V7（全量对齐）**

1. **官方 tpl** — `nunjucks_lite` + `--official-tpl`
2. **Harbor Docker 桥** — `harbor_cli`（status / validate / build-smoke）
3. **四子集齐全** — office/code/web/sec
4. **Casdoor JWT + Milvus REST** — 企业客户端
5. **项目空间 / Office 产物 / 审计**
6. **SMTP + webhook**
7. **Compose 7×24** — `deploy/docker-compose.workbuddy.yml`
8. **验收** — `scripts/verify_full.py`

**V8（端到端交付）**

1. **Octop 后端真出答** — `octop run` 在 Windows 起来，`POST /api/auth/login` 出 JWT，`WS /api/agents/{id}/chat/ws` 收到 DeepSeek 流式 token；DeepSeek provider 通过 `scripts/seed_deepseek_provider.py` 注入
2. **mobile PWA 静态落盘** — `mobile/` Vite build → `dist/mobile-dist.zip`，默认 baseUrl `http://127.0.0.1:8088`，`mobile/icons/icon-{192,512}.png` 用熊宝品牌图替换
3. **Desktop Octop 接管 IM** — 设置页新增「Octop 连接」(`OctopBridgeSettings.tsx`)，IPC 通道 `OctopBridgeIpc.{ConfigGet,ConfigSet,Login,ListAgents}`，sqliteStore 持久化 `octop_base_url` / `octop_jwt` / `octop_agent_id` / `use_octop_for_im`；`OctopChatClient` 已能解析 server 的 `token` 帧（harness 当前 stream 形态），`chunk` 保留兼容
4. **三件交付物** — `dist/octop-1.0.0-py3-none-any.whl` + `dist/install-octop.bat` + `dist/mobile-dist.zip`；NSIS `熊宝Agent-Setup-*.exe` 需要 `bun` 与 channel/engram runtime（首次 ~30-60 min 拉取），electron-builder.json / nsis-installer.nsh 已从「知远」改为「熊宝 Agent」
5. **验收脚本** — `scripts/deliver_smoke.py`（纯 stdlib）7/7 PASS：health / login / agents / WS 出答 / mobile npm test / mobile zip / wheel+bat
6. **IM 真渠道** — Phase D 挂起，需用户提供钉钉/企微/飞书凭证

边界：闭源 Electron / 腾讯云 SaaS 不复制；UI → Octop Dashboard；托管 → Compose/systemd。

## 目录要点

```
octop/
  contrib/workbuddy/          # wb2octop + team + bench + teach + routine + V7
  src/octop/.../library/      # 转换后的专家包
vendor/
  workbuddy-experts/
  workbuddyskills/
  workbuddy-bench/            # 官方评测框架 + 四子集数据集
  workbuddy-cdn-snapshot/
  RongXinAI/
tests/contrib/workbuddy/
scripts/verify_all.py
scripts/verify_full.py         # V7 全量验收
scripts/fetch_bench_subsets.ps1
scripts/fetch_cdn_snapshot.ps1
deploy/docker-compose.workbuddy.yml
TASKBOARD.md
```

> 跨层联调（RongXinAI Desktop ↔ Octop ↔ Console）请阅读
> [`docs/INTEGRATION.md`](docs/INTEGRATION.md)。性能门禁见
> [`docs/performance-baselines.md`](docs/performance-baselines.md)。

## 快速验证（Windows / 无 pytest）

```powershell
cd "D:\AI编程库\项目库\进行中的项目\xiongbao agent"
python -S scripts\verify_full.py
```

等价分步：

```powershell
python -S tests\contrib\workbuddy\run_tests.py
python -S tests\contrib\workbuddy\test_team_runtime.py
python -S tests\contrib\workbuddy\test_bench.py
python -S -m octop.contrib.workbuddy.bench.cli --sample 50 --out-dir artifacts\bench
python -S tests\contrib\workbuddy\demo_stock_partner.py
```

通过标准：单元测试全绿；smoke-50 **pass rate ≥ 90%**；若本机 Ollama 可用则 live team 真调通过。

## 本地 LLM 真调（Ollama）

前置：Ollama 已安装且 `http://127.0.0.1:11434` 可访问。

### 按需求匹配并下载

| profile | 场景 | 推荐模型 | 约体积 |
|---------|------|----------|--------|
| `smoke` | CI / 2 人冒烟 | `qwen2.5:1.5b` | ~1 GB |
| `team` | 中文 Team（2–4 人，默认） | `qwen2.5:3b` | ~2 GB |
| `team-full` | 6 人专家团 | `qwen2.5:7b` | ~4.7 GB |
| `strong` | 更高质量综合 | `qwen2.5:14b` | ~9 GB |

```powershell
$env:OLLAMA_MODELS = "$env:USERPROFILE\.ollama\models"
# 只匹配
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4
# 匹配并拉取
python -S -m octop.contrib.workbuddy.team.match_cli --profile team --vram-gb 4 --pull
# 查看目录
python -S -m octop.contrib.workbuddy.team.match_cli --list
```

已安装模型若档位低于需求（例如只要有 `1.5b` 但 profile=`team`），会推荐并拉取更高档，不会误用过弱模型。

若 `OLLAMA_MODELS` 指向损坏的 junction（例如错误的 `C:\ollama_models`），服务会起不来。可临时：

```powershell
$env:OLLAMA_MODELS = "$env:USERPROFILE\.ollama\models"
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" serve
```

跑 Team 真调（默认最多 2 名成员；`team` 档用 3b）：

```powershell
$env:WB_LLM_MODEL = "qwen2.5:3b"
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --max-members 2
```

环境变量：`WB_LLM_BASE_URL`（默认 `http://127.0.0.1:11434/v1`）、`WB_LLM_MODEL`、`WB_LLM_API_KEY`。

## V2 Teach → Routine

```powershell
# 单元测试
python -S tests\contrib\workbuddy\test_teach_routine.py

# 端到端 demo（可选 --llm 润色）
python -S -m octop.contrib.workbuddy.teach_cli demo
python -S -m octop.contrib.workbuddy.teach_cli demo --llm

# 列表 / 审批 / 创建 / 执行 / 润色
python -S -m octop.contrib.workbuddy.teach_cli list
python -S -m octop.contrib.workbuddy.teach_cli polish --name notion-pr-to-feishu --llm
python -S -m octop.contrib.workbuddy.teach_cli approve --name notion-pr-to-feishu
python -S -m octop.contrib.workbuddy.teach_cli create-routine --skill notion-pr-to-feishu --bot-id bot-1
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode dry
```

模式：`dry`（不落地副作用）→ `test`（需确认）→ `live`。高风险步骤需审批；默认每 bot ≤50 条 Routine。

CDP / Connectors：

```powershell
python -S tests\contrib\workbuddy\test_cdp_live.py
python -S tests\contrib\workbuddy\test_connectors_replay.py

# Chrome 需 --remote-debugging-port=9222
python -S -m octop.contrib.workbuddy.teach_cli cdp-record --url https://example.com --seconds 20
python -S -m octop.contrib.workbuddy.teach_cli connectors
python -S -m octop.contrib.workbuddy.teach_cli run --routine-id <id> --mode live `
  --live-runner --cdp-replay --outbound
```

Env：`WB_NOTION_TOKEN`、`WB_FEISHU_WEBHOOK` 或 `WB_FEISHU_APP_ID`/`SECRET`/`RECEIVE_ID`、`WB_ALLOW_OUTBOUND=1`。
开放平台目标：`feishu:chat/<chat_id>`、`feishu:open_id/<id>`、`feishu:open`。

调度（每分钟由系统任务调用即可，无需常驻进程）：

```powershell
python -S tests\contrib\workbuddy\test_routine_scheduler.py
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine due
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine tick --mode dry
```

详见 `DELIVERABLE.md`。

## V3 Goal / Craft

```powershell
python -S tests\contrib\workbuddy\test_goal_craft.py
python -S -m octop.contrib.workbuddy.goal_cli demo
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md 并通知飞书" --llm
python -S -m octop.contrib.workbuddy.goal_cli run --goal "写入 report.md 并通知飞书" --approve-all
```

流程：规则规划 steps+验收标准 → 可选 `--llm` 润色文案 → LiveStepRunner 执行 → 逐条验收 → 失败可重试。

## SkillHub 运行时绑定

扫描 `vendor/workbuddyskills/skills/*/SKILL.md`，enable / compose / 生成 prompt pack；可注入 Team live 与 Goal。

```powershell
python -S tests\contrib\workbuddy\test_skillhub.py
python -S -m octop.contrib.workbuddy.skills_cli list
python -S -m octop.contrib.workbuddy.skills_cli search diagnose
python -S -m octop.contrib.workbuddy.skills_cli enable diagnose
python -S -m octop.contrib.workbuddy.skills_cli compose --id diagnose
python -S -m octop.contrib.workbuddy.skills_cli scripts --id diagnose
# Goal 绑定 skill：
python -S -m octop.contrib.workbuddy.goal_cli plan --goal "写入 weekly.md" --skill diagnose
# Team 真调时绑定 skill：
python -S -m octop.contrib.workbuddy.team.live_cli --expert StockPartnerTeam --skill diagnose --max-members 2
```

## V4 验收

```powershell
python -S scripts\verify_v4.py
# Outbox 失败重试（需真实凭证时加 --outbound）：
python -S -m octop.contrib.workbuddy.teach_cli retry-outbox --work-dir artifacts\goal_craft\work\<id> --list-only
```

## Windows 计划任务（Routine tick）

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_routine_tick.ps1
```

详见 `scripts/windows/README.md`。

## 转换专家（如需重跑）

```powershell
python -S -m octop.contrib.workbuddy.cli --vendor vendor --output octop\src\octop\infra\agents\experts\library
```

## 官方 workbuddy-bench（可选）

拉取 Office 50 题（约 3–10MB，gitignore）：

```powershell
powershell -File scripts\fetch_office_dataset.ps1
# 或 Git Bash / WSL:
# cd vendor/workbuddy-bench && ./scripts/dataset/fetch-dataset.sh office
```

本仓库 **smoke-50** 不依赖 HF。Office 有两条路径：

1. **llm_lite（本仓库）** — 本地 LLM 作答 + 启发式/judge，无需 Docker  
2. **全量 Harbor（上游）** — 需 Docker + 官方 verifier

```powershell
python -S -m octop.contrib.workbuddy.bench.cli --office --list-office --dry-sample-only
python -S -m octop.contrib.workbuddy.bench.cli --office --live-llm --limit 3 --no-judge --pass-rate 0.3
python -S scripts\verify_v5.py
```

## 环境要求

- Python **3.11+**（Octop 上游标 3.12+；本桥接层用 `python -S` 可在 3.11 跑通）
- 完整跑 Octop 服务：按 `octop/AGENTS.md`（uv、Node 等）
- 可选：Docker（官方 bench）

## License

- Octop / 本桥接代码：MIT
- WorkBuddy 专家资产：见 `vendor/` 各仓库 NOTICE（MIT / 原作者声明）
- workbuddy-bench：腾讯评测许可，见该仓库 LICENSE
