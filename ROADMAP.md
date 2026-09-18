# ROADMAP — xiongbao-agent

自主连推进度板。Agent 按阶段连续实现与提交，**不按「你问一句做一段」节奏停顿**。

## 已交付

| 阶段 | 内容 | 状态 |
|---|---|---|
| V1 | wb2octop / Team / smoke-50 / 本地 LLM | ✅ |
| V2 | Teach→Routine / cron tick / CDP / Notion+飞书 webhook | ✅ |
| V3 | Goal/Craft / SkillHub prompt 绑定 / Goal `--llm` / 飞书 open API | ✅ |
| V4 | 脚本沙箱 / Goal `--skill` / outbox retry / verify_v4 | ✅（连推完成） |

## V5 — 后续（自动开干）

1. Harbor 子集 live LLM 评分接线（可选，需题库）
2. Windows 计划任务示例（`tick` 调度）
3. Casdoor / Milvus / systemd — **企业包装，默认跳过**（需你明确点名）

## 工作方式

- 每完成一项：测试绿 → commit → push → 立刻下一项
- 不中途空等「下一步」确认
- 不可逆/外发仍受 `WB_ALLOW_OUTBOUND` 门禁；不写真实密钥进仓库
