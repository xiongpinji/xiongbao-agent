# ROADMAP — xiongbao-agent

自主连推进度板。Agent 按阶段连续实现与提交，**不按「你问一句做一段」节奏停顿**。

## 已交付

| 阶段 | 内容 | 状态 |
|---|---|---|
| V1 | wb2octop / Team / smoke-50 / 本地 LLM | ✅ |
| V2 | Teach→Routine / cron tick / CDP / Notion+飞书 webhook | ✅ |
| V3 | Goal/Craft / SkillHub prompt 绑定 / Goal `--llm` / 飞书 open API | ✅ |
| V4 | 脚本沙箱 / Goal `--skill` / outbox retry / verify_v4 | ✅ |
| V5.1 | Windows 计划任务 `tick` 示例 | ✅ |
| V5.2 | Office 题库拉取 + **llm_lite** 本地评分（无 Docker Harbor） | ✅ |
| V5.3 | systemd 单元 + Casdoor/Milvus **文档门禁** | ✅ |
| V6.1 | Ask / Plan / Craft 模式装配器 + CLI | ✅ |
| V6.2 | 工作区 SOUL/USER/MEMORY 注入 Team/Goal | ✅ |
| V6.3 | 钉钉/企微 webhook + 103 连接器目录 CLI | ✅ |
| V6.4 | 专家自动路由（tags/关键词） | ✅ |
| V6.5 | Bench 全子集 list + `fetch_bench_subsets.ps1` | ✅ |
| V6.6 | builtin-skills 进 SkillHub | ✅ |
| V6.7 | Casdoor/Milvus 软探测 stub | ✅ |
| V6.8 | `scripts/verify_all.py` 一键验收 | ✅ |

## 后续（非阻塞）

1. 全量 Harbor Docker 评分（code/web/sec + office 官方 verifier）— 需 Docker 环境
2. Casdoor / Milvus **JWT/RAG 运行时接线**（当前为 env 探测 + 文档约定）

## 工作方式

- 每完成一项：测试绿 → commit → push → 立刻下一项
- 不中途空等「下一步」确认
- 不可逆/外发仍受 `WB_ALLOW_OUTBOUND` 门禁；不写真实密钥进仓库

## 看板

见根目录 `TASKBOARD.md`。
