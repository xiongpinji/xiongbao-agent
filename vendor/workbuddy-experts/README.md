# WorkBuddy Experts · 提示词工程参考资产集

> 从腾讯 WorkBuddy 4.22.16 客户端整理的 **246 位 AI 专家提示词** + **7 个 Nunjucks 系统模板** + **2 个内置 skill**，附完整逆向分析报告。

![experts](https://img.shields.io/badge/experts-246-blue) ![categories](https://img.shields.io/badge/categories-13-green) ![source](https://img.shields.io/badge/source-WorkBuddy_4.22.16-orange) ![license](https://img.shields.io/badge/curation-MIT-lightgrey)

English version: [`README.en.md`](README.en.md)

---

## ⚠️ 免责声明（请先读完）

1. **资产来源**：本仓库内容来自 WorkBuddy macOS 客户端的**静态分析** + 公开 Tencent COS（`acc-1258344699.cos.accelerate.myqcloud.com`）**匿名 GET**。**不涉及破解、不修改任何 app 文件、不绕过任何鉴权**。
2. **版权归属**：
   - 大部分专家提示词派生自上游 MIT 项目 [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents)；
   - 「腾讯专区」专家、本地化分类、`workbuddy-*.tpl` 模板的腾讯定制部分，版权归 **腾讯**；
   - 本仓库的整理、索引、报告（`README*.md`、`PROMPTS.md`、`experts/INDEX.md`）以 **MIT** 发布，详见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。
3. **使用边界**：**仅供个人学习提示词工程**。禁止批量公开转载或商业再分发。如需在生产环境使用，请自行评估并联系版权方。
4. **内容警示**：`templates/` 中嵌入了中国大陆区域化的内容安全条款（涉政、色情、隐私、虚假信息等审查规则），二次使用前请知悉并自行评估合规性。
5. **不附属声明**：本仓库与腾讯 / WorkBuddy 产品团队 **没有任何官方关联**。"WorkBuddy" 是腾讯商标。

---

## 这是什么 / 不是什么

| | |
|---|---|
| ✅ **是** | 提示词工程的参考案例集；246 位领域专家的 system prompt 全文；Nunjucks 模板拼装机制的真实样本；WorkBuddy 客户端架构的逆向报告 |
| ❌ **不是** | WorkBuddy 的替代品；可运行的 Electron 应用；腾讯官方 SDK；任何形式的腾讯出品物 |

---

## 目录布局

```
workbuddy-experts/
├── README.md                ← 本文件（先读这个）
├── README.en.md             ← English version
├── PROMPTS.md               ← 完整逆向分析报告（架构、IPC、COS、缓存路径）
├── LICENSE                  ← MIT（仅覆盖整理工作）
├── NOTICE                   ← 上游 + 腾讯部分版权说明
├── templates/               ← 7 个核心 .tpl 提示词模板（系统级，与具体专家无关）
├── builtin-skills/          ← 客户端内置 2 个 skill
└── experts/
    ├── manifest.json        ← 246 位专家的完整 manifest（来自 COS）
    ├── INDEX.md             ← 246 位专家的可读索引（按分类，带相对链接）
    └── prompts/plugins/<plugin>/agents/<expert>.md
                              ← 246 个专家的完整提示词正文
```

> `asar/` 目录（WorkBuddy 客户端解包源码，~495 MB）**未提交**。如需复现，参考 [`PROMPTS.md`](PROMPTS.md) 第 5 节自行从本机 `/Applications/WorkBuddy.app` 解包。

---

## 核心架构：提示词如何组装

WorkBuddy 用 Nunjucks 引擎按当前模式 + 是否绑定专家，每次对话动态拼装最终 system prompt：

```
最终 system prompt
└── 在 templates/ 中选一个根模板
    ├── 普通对话 → workbuddy-prompt.tpl              （主系统提示词）
    ├── 绑定专家  → workbuddy-expert-prompt.tpl       （Role Override + 注入 {{ ExpertPrompt }}）
    ├── 专家工作  → workbuddy-expert-working-prompt.tpl
    └── 纯问答    → workbuddy-ask-prompt.tpl
    ↓ 注入变量
    ├── {{ ExpertPrompt }}          ← 专家正文（来自 experts/prompts/...）
    ├── {{ SoulContent }}           ← 工作区 SOUL.md 人设（可选）
    ├── {{ UserContent }}           ← 工作区 USER.md 用户档案
    ├── {{ IdentityContent }}       ← workspace IDENTITY.md
    ├── {{ WorkingMemoryContent }}  ← 短期工作记忆
    ├── {{ UserMemoryContent }}     ← 长期用户记忆
    └── {{ ClawMemory_1/2/3 }}      ← 多段插入记忆
    ↓ 末尾按工作模式追加
    └── system-reminder.tpl / ask-mode-reminder.tpl / craft-mode-reminder.tpl
```

**三个关键设计点**：

- **Role Override**：`workbuddy-expert-prompt.tpl` 第 36 行明文声明"注入的专家定义优先级高于一切已建立的人设/身份"——这就是 246 位专家能"接管"对话风格的实现机制。
- **三种工作模式**：Craft（自由编辑）/ Plan（规划）/ Ask（只读问答），分别由不同的 reminder 末尾追加。
- **强制内容安全**：每个模板都嵌入 `<content_policy>` 与 `<personal_files_safety>`（8 条文件保护规则、禁止 `rm -rf`、批量最多 10 个、必须走系统垃圾桶）。

---

## 内容概览

### 1. `templates/` — 7 个 Nunjucks 模板（~136 KB）

| 文件 | 大小 | 用途 |
|---|---:|---|
| [`workbuddy-prompt.tpl`](templates/workbuddy-prompt.tpl) | 35 KB | 默认主系统提示词（无专家时） |
| [`workbuddy-expert-prompt.tpl`](templates/workbuddy-expert-prompt.tpl) | 33 KB | 绑定专家根模板（含 Role Override） |
| [`workbuddy-expert-working-prompt.tpl`](templates/workbuddy-expert-working-prompt.tpl) | 37 KB | 专家工作模式变体 |
| [`workbuddy-ask-prompt.tpl`](templates/workbuddy-ask-prompt.tpl) | 11 KB | Ask 模式精简版（只读） |
| [`ask-mode-reminder.tpl`](templates/ask-mode-reminder.tpl) | 582 B | 末尾追加 `<ask_mode>`，禁写 |
| [`craft-mode-reminder.tpl`](templates/craft-mode-reminder.tpl) | 254 B | 末尾追加 `<craft_mode>`，允写 |
| [`system-reminder.tpl`](templates/system-reminder.tpl) | 37 B | 运行时填充占位 |

### 2. `builtin-skills/` — 2 个客户端内置 skill

| Skill | 用途 |
|---|---|
| [`skill-creator`](builtin-skills/skill-creator/SKILL.md) | 创建 / 修改 / 验证 skill，含打包成 `.skillpkg` 的脚本 |
| [`buddy-multimodal-generation`](builtin-skills/buddy-multimodal-generation/SKILL.md) | 通过腾讯云调用多模态模型（图像 / 3D / 视频） |

### 3. `experts/` — 246 位专家（~3.6 MB）

| 分类 | 数量 | 分类 | 数量 |
|---|---:|---|---:|
| 腾讯专区 (Tencent Zone) | 17 | 营销增长 (Marketing Growth) | 29 |
| 产品设计 (Product Design) | 17 | 内容创作 (Content Creative) | 27 |
| 技术工程 (Engineering) | 29 | 销售商务 (Sales Commerce) | 10 |
| 金融投资 (Finance Investment) | 23 | 运营人力 (Operations HR) | 6 |
| 游戏空间 (Game & Spatial) | 24 | 项目质量 (Project Quality) | 23 |
| 数据智能 (Data & AI) | 20 | 法务安全 (Security Compliance) | 14 |
| 行业顾问 (Industry Consultant) | 7 | **合计** | **246** |

完整可点击索引见 [`experts/INDEX.md`](experts/INDEX.md)，结构化字段（tags / quickPrompts / defaultInitPrompt / avatar）见 [`experts/manifest.json`](experts/manifest.json)。

### 4. [`PROMPTS.md`](PROMPTS.md) — 完整逆向报告

涵盖：客户端架构、IPC 通道清单、专家市场 COS 路径、排行榜 API、客户端缓存位置、复现操作建议、风险与使用边界。

---

## 怎么用

```bash
# 1. 浏览全部专家（按分类 + 相对链接）
open experts/INDEX.md

# 2. 查某个专家的 manifest 字段（tags / quickPrompts / 默认初始 prompt）
jq '.experts[] | select(.id=="UIDesigner")' experts/manifest.json

# 3. 读某个专家的提示词正文
cat experts/prompts/plugins/ui-designer/agents/ui-designer.md

# 4. 学习模板拼装机制
less templates/workbuddy-prompt.tpl
less templates/workbuddy-expert-prompt.tpl  # 看 Role Override 注入位置

# 5. 跟踪上游变更（manifest 的 lastUpdated 字段）
curl -s https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/expert_center.json | jq '.lastUpdated'
```

---

## 关键技术点速查

| 项 | 值 / 路径 |
|---|---|
| 提示词覆盖机制 | `workbuddy-expert-prompt.tpl` 第 36 行 Role Override 声明 |
| 客户端数据目录 | `~/.workbuddy/`（含 `workbuddy.db`、专家缓存等） |
| MCP 配置文件 | `~/.workbuddy/mcp.json` |
| 专家市场 COS 基址 | `https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/` |
| 排行榜 API | `/console/expert/ranking`（需登录态，**本仓库不提供数据**） |
| Manifest 路径 | `/expert_center.json`（公开匿名可访问） |
| 客户端缓存 | `~/.workbuddy/app/cache/experts/manifest.json` |

---

## 复现 `asar/` 目录

`asar/` 是 WorkBuddy 客户端 `app.asar` 的完整解包结果（~495 MB，含 node_modules / renderer chunks），不在 git 中。如需自行复现：

1. 安装 [WorkBuddy](https://copilot.tencent.com/) 4.22.16（或同等版本）
2. 用 `npx asar extract /Applications/WorkBuddy.app/Contents/Resources/app.asar ./asar/`
3. 详细路径与关键代码位置见 [`PROMPTS.md`](PROMPTS.md) 第 1 节、第 5 节

---

## 相关资源

- 上游提示词源项目：[`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents)（MIT）
- WorkBuddy 官方：[copilot.tencent.com](https://copilot.tencent.com/)
- 完整逆向报告：[`PROMPTS.md`](PROMPTS.md)
- 法律边界：[`LICENSE`](LICENSE) / [`NOTICE`](NOTICE)

---

## License

整理、索引、报告部分以 **MIT** 发布。专家提示词正文与 WorkBuddy 模板版权归上游与腾讯所有。详见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。
