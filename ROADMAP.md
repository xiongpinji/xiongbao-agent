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

## V5 — 剩余（可选 / 阻塞）

1. Harbor 子集 live LLM 评分 — **阻塞**：`vendor/workbuddy-bench` 无 office 题库；需自行 `fetch-dataset.sh office` 后再接线
2. Casdoor / Milvus / systemd — **企业包装，默认跳过**（需明确点名）

## 工作方式

- 每完成一项：测试绿 → commit → push → 立刻下一项
- 不中途空等「下一步」确认
- 不可逆/外发仍受 `WB_ALLOW_OUTBOUND` 门禁；不写真实密钥进仓库
