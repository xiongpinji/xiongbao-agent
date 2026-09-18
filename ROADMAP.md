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

## 产品边界（无法像素级复制）

| 项 | 等价交付 |
|---|---|
| 腾讯 Electron / QClaw 桌面壳 | Octop Dashboard + WorkBuddy Console + CLI |
| 腾讯云托管 SaaS | Docker Compose / systemd 私有化 7×24 |
| 小程序 / 移动端 / 计费 | 不做 |
| 腾讯文档 / IMA / 乐享 | 本地 knowledge 适配 |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v9.py
python -S scripts\verify_full.py
```
