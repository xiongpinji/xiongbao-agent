# 剩余工作规划 — xiongbao-agent 距交付差距

> 本文档盘点项目当前**尚未完成**的工作，给出工作分解、优先级与工作量估算。
> 项目结构：`octop/`（Python 后端 + Web Dashboard）+ `vendor/RongXinAI/`（Electron + React 桌面应用）

---

## 📊 项目当前总体状态

| 模块 | 状态 | 说明 |
|------|------|------|
| octop 后端（V1–V18） | ✅ 已完成 | 全部 18 个版本已交付，有 verify 脚本可重复验证 |
| octop Web Dashboard | ✅ 已完成 | 三栏用户壳 + 项目空间 + 多租户 |
| octop 工作流/调度/通道/技能 | ✅ 已完成 | 钉钉/企微/微信/QQ/飞书通道 + SkillHub + Harbor 桥 |
| **vendor/RongXinAI 桌面应用** | 🟡 **部分完成** | 拉取了上游仓库，本会话只做了 4 个增强模块 |
| 端到端联调（两端联通） | ❌ 未做 | octop ↔ RongXinAI 之间无桥接 |
| 部署/CI/CD | 🟡 部分 | 有 Compose / systemd，但 Windows 端打包未跑通 |

**已交付**：octop 后端的 V1–V18（18 个里程碑）。
**本会话额外贡献**：RongXinAI 4 个增强模块（品牌主题/积分/语音/响应式），63 个测试全过。
**真正未完成的**：分两大部分——RongXinAI 子项目大量功能没碰 + 两端联调 + 测试存量修复。

---

## 🎯 剩余工作分解（按优先级）

### P0 — 阻塞核心体验的必修项

#### 1. RongXinAI **核心 Agent 运行时联通**
- **现状**：仓库代码完整（Pi runtime adapter、agentEngine、cc-connect 侧车、cowork 会话管理都在），但**完全没有验证过能跑通端到端流程**。
- **要做**：
  - 跑通 `npm run electron:dev`，能启动 Electron 主窗口
  - 跑通新建 Cowork 会话 → 发 prompt → 收到流式响应 → 工具权限弹窗 → 结束会话
  - 跑通 Pi runtime 适配器真正工作（不是 mock）
- **工作量**：1–2 天深度调试（依赖环境：node-pty 编译、Electron、模型 API key）
- **风险**：高——这是上