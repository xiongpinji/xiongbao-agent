# ROADMAP — xiongbao-agent

自主连推进度板。Agent 按阶段连续实现与提交，**不按「你问一句做一段」节奏停顿**。

## 已交付

| 阶段 | 内容 | 状态 |
|---|---|---|
| V1–V5 | 专家 / Team / Teach·Routine / Goal·Craft / SkillHub / Office llm_lite / systemd | ✅ |
| V6 | Ask·Plan·Craft / 记忆 / 钉钉企微 / 路由 / bench 子集 / builtin / 软探测 / verify_all | ✅ |
| **V7.1** | 官方 Nunjucks `.tpl` → `nunjucks_lite` + `--official-tpl` | ✅ |
| **V7.2** | Harbor Docker 桥（status / validate / build-smoke） | ✅ |
| **V7.3** | sec 子集拉取（60 题） | ✅ |
| **V7.4** | Casdoor JWT 校验 + Milvus REST RAG 客户端 | ✅ |
| **V7.5** | 项目空间（共享目录 + Skill 沉淀） | ✅ |
| **V7.6** | Office 产物管线（md/html/csv + 可选 docx/xlsx/pptx） | ✅ |
| **V7.7** | SMTP 邮件 + 通用 webhook | ✅ |
| **V7.8** | 审计 JSONL | ✅ |
| **V7.9** | `deploy/docker-compose.workbuddy.yml` 7×24 | ✅ |
| **V7.10** | CDN/docs 快照脚本 + 已拉取 | ✅ |
| **V7.11** | `scripts/verify_full.py` | ✅ |

## 产品边界（无法像素级复制）

| 项 | 等价交付 |
|---|---|
| 腾讯 Electron / QClaw 桌面壳 | Octop Dashboard + CLI 全家桶 |
| 腾讯云托管 SaaS | Docker Compose / systemd 私有化 7×24 |
| 官方 Harbor 全量打分 CLI | Docker 桥 + 数据集齐全；完整 CLI 需本机 Python ≥3.12 + `uv sync` |

## 验收

```powershell
python -S scripts\verify_full.py
# 可选：python -S scripts\verify_full.py --harbor-build
```

## 看板

见 `TASKBOARD.md`。
