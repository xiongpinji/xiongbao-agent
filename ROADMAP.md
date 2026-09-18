# ROADMAP — xiongbao-agent

自主连推进度板。Agent 按阶段连续实现与提交，**不按「你问一句做一段」节奏停顿**。

## 已交付

| 阶段 | 内容 | 状态 |
|---|---|---|
| V1–V5 | 专家 / Team / Teach·Routine / Goal·Craft / SkillHub / Office llm_lite / systemd | ✅ |
| V6 | Ask·Plan·Craft / 记忆 / 钉钉企微 / 路由 / bench 子集 / builtin / 软探测 / verify_all | ✅ |
| V7 | 官方 tpl / Harbor 桥 / 四子集 / Casdoor+Milvus 客户端 / 项目·Office·审计·Compose | ✅ |
| V8 | Harbor uv sync + dry-run / Compose 常驻 / Console+Hub | ✅ |
| V9 | 任务生命周期 / 权限 / 数据 / 模型档案 / worktree / 微信QQ / 资料库 / 灵感 / KB / 共写 / 通道桥 / Skill 安装扫描 / Console v2 / Harbor 评分钩子 / 审计挂钩 | ✅ |
| V10 | Task→Goal 执行 / Policy 门禁 / 模型档案注入 / Inbox 轮询 / Skill 注册目录 / KB 召回 / 多根打包 / Task+worktree / Cowrite→Library / Console Runtime | ✅ |
| V11 | 多租户注册 / 路径隔离 / Console JWT / 配额 / 租户备份 / Milvus 命名空间 / Casdoor 换发 / Caddy 生产 Compose / Runbook | ✅ |
| Go-Live | 无域名 P0 勾选签字 + 正式开户/异地备份手册 | ✅ |
| V12 | Web 三栏用户壳 + Task/Workspace/Skills API + verify_v12 | ✅ |
| V13 | 附件上传 / 富预览 / Enterprise 状态 / Harbor dry-run + verify_v13 | ✅ |
| V14 | Casdoor+Milvus 本地联调 / docx·xlsx 预览 / Harbor score + verify_v14 | ✅ |
| V15 | Casdoor OIDC 换发联调 / pptx 预览 / Harbor live 评分 | ✅ |
| V16 | Harbor 四子集 smoke / Casdoor 生产清单 / Caddy tls internal | ✅ |
| V17 | 用户壳四维质量：人话执行/默认真跑/CSS 抽出/登录与交互 100%·视觉≥95% | ✅ |

## 产品边界（无法像素级复制）

| 项 | 等价交付 |
|---|---|
| 腾讯 Electron / QClaw 桌面壳 | **Web 三栏壳** `/` + 运维 `/ops.html` + CLI |
| 腾讯云托管 SaaS | Docker Compose / systemd 私有化 7×24（多租户） |
| 小程序 / 移动端 / 计费 | 不做（仅配额钩子） |
| 腾讯文档 / IMA / 乐享 | 本地 knowledge 适配 |

一致性评分见 `deploy/enterprise/WORKBUDDY_PARITY_AUDIT.md`。

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v17.py
python -S scripts\verify_v16.py
python -S scripts\verify_v11.py
```
