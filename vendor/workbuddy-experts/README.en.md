# WorkBuddy Experts · Prompt Engineering Reference Archive

> **246 AI expert prompts** + **7 Nunjucks system templates** + **2 built-in skills**, curated from Tencent WorkBuddy 4.22.16, with a complete reverse-engineering report.

![experts](https://img.shields.io/badge/experts-246-blue) ![categories](https://img.shields.io/badge/categories-13-green) ![source](https://img.shields.io/badge/source-WorkBuddy_4.22.16-orange) ![license](https://img.shields.io/badge/curation-MIT-lightgrey)

中文版: [`README.md`](README.md)

---

## ⚠️ Disclaimer (read this first)

1. **Provenance**: All content is obtained via **static analysis** of the WorkBuddy macOS client + **anonymous public GET** from Tencent COS (`acc-1258344699.cos.accelerate.myqcloud.com`). **No cracking, no app modification, no auth bypass.**
2. **Copyright**:
   - Most expert prompts are derived from the upstream MIT project [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents);
   - The "Tencent Zone" experts, localized categories, and Tencent-customized parts of `workbuddy-*.tpl` templates are copyrighted by **Tencent**;
   - The curation work in this repo (`README*.md`, `PROMPTS.md`, `experts/INDEX.md`) is released under **MIT** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
3. **Usage boundary**: **For personal study of prompt engineering only.** Bulk public republication or commercial redistribution is prohibited. Contact the copyright holders before any production use.
4. **Content warning**: `templates/` embeds China-Mainland-specific content safety clauses (political topics, adult content, privacy, disinformation review rules). Evaluate compliance implications before reuse.
5. **No affiliation**: This repository has **no official affiliation** with Tencent or the WorkBuddy product team. "WorkBuddy" is a Tencent trademark.

---

## What this is / is not

| | |
|---|---|
| ✅ **Is** | A reference archive for prompt engineering; full system prompts of 246 domain experts; a real-world sample of Nunjucks template composition; a reverse-engineering report on the WorkBuddy client |
| ❌ **Is not** | A WorkBuddy replacement; a runnable Electron app; an official Tencent SDK; an official Tencent product in any form |

---

## Repository layout

```
workbuddy-experts/
├── README.md                ← Chinese version
├── README.en.md             ← this file
├── PROMPTS.md               ← full reverse-engineering report (architecture, IPC, COS, cache paths)
├── LICENSE                  ← MIT (covers curation work only)
├── NOTICE                   ← upstream + Tencent copyright notices
├── templates/               ← 7 core .tpl prompt templates (system-level, expert-agnostic)
├── builtin-skills/          ← 2 built-in client skills
└── experts/
    ├── manifest.json        ← full manifest of 246 experts (from COS)
    ├── INDEX.md             ← human-readable index by category, with relative links
    └── prompts/plugins/<plugin>/agents/<expert>.md
                              ← full prompt text for each of 246 experts
```

> The `asar/` directory (unpacked WorkBuddy client source, ~495 MB) is **not committed**. To reproduce it, follow [`PROMPTS.md`](PROMPTS.md) §5 and extract from your own local `/Applications/WorkBuddy.app`.

---

## Core architecture: how prompts are composed

WorkBuddy uses Nunjucks to dynamically assemble the final system prompt for every conversation, based on the current mode and whether an expert is bound:

```
Final system prompt
└── Pick one root template from templates/
    ├── normal chat → workbuddy-prompt.tpl              (default system prompt)
    ├── with expert → workbuddy-expert-prompt.tpl       (Role Override + inject {{ ExpertPrompt }})
    ├── expert work → workbuddy-expert-working-prompt.tpl
    └── ask only    → workbuddy-ask-prompt.tpl
    ↓ inject variables
    ├── {{ ExpertPrompt }}          ← expert body (from experts/prompts/...)
    ├── {{ SoulContent }}           ← workspace SOUL.md persona (optional)
    ├── {{ UserContent }}           ← workspace USER.md user profile
    ├── {{ IdentityContent }}       ← workspace IDENTITY.md
    ├── {{ WorkingMemoryContent }}  ← short-term working memory
    ├── {{ UserMemoryContent }}     ← long-term user memory
    └── {{ ClawMemory_1/2/3 }}      ← multi-segment inserted memory
    ↓ append by working mode
    └── system-reminder.tpl / ask-mode-reminder.tpl / craft-mode-reminder.tpl
```

**Three key design points**:

- **Role Override**: Line 36 of `workbuddy-expert-prompt.tpl` explicitly declares that "the injected expert definition takes priority over any previously established persona/identity" — this is the mechanism that lets all 246 experts truly "take over" the conversation style.
- **Three working modes**: Craft (free editing) / Plan (planning) / Ask (read-only Q&A), appended via different reminder files.
- **Enforced content safety**: Every template embeds `<content_policy>` and `<personal_files_safety>` (8 file-protection rules, ban on `rm -rf`, max 10 items per batch, mandatory system trash).

---

## What's inside

### 1. `templates/` — 7 Nunjucks templates (~136 KB)

| File | Size | Purpose |
|---|---:|---|
| [`workbuddy-prompt.tpl`](templates/workbuddy-prompt.tpl) | 35 KB | Default system prompt (no expert bound) |
| [`workbuddy-expert-prompt.tpl`](templates/workbuddy-expert-prompt.tpl) | 33 KB | Expert-bound root template (with Role Override) |
| [`workbuddy-expert-working-prompt.tpl`](templates/workbuddy-expert-working-prompt.tpl) | 37 KB | Expert in "working mode" variant |
| [`workbuddy-ask-prompt.tpl`](templates/workbuddy-ask-prompt.tpl) | 11 KB | Ask-mode lean version (read-only) |
| [`ask-mode-reminder.tpl`](templates/ask-mode-reminder.tpl) | 582 B | Appends `<ask_mode>`, forbids writes |
| [`craft-mode-reminder.tpl`](templates/craft-mode-reminder.tpl) | 254 B | Appends `<craft_mode>`, permits writes |
| [`system-reminder.tpl`](templates/system-reminder.tpl) | 37 B | Runtime-filled placeholder |

### 2. `builtin-skills/` — 2 built-in client skills

| Skill | Purpose |
|---|---|
| [`skill-creator`](builtin-skills/skill-creator/SKILL.md) | Create / modify / validate a skill, including `.skillpkg` packaging scripts |
| [`buddy-multimodal-generation`](builtin-skills/buddy-multimodal-generation/SKILL.md) | Image / 3D / video generation via Tencent Cloud multimodal models |

### 3. `experts/` — 246 experts (~3.6 MB)

| Category | Count | Category | Count |
|---|---:|---|---:|
| Tencent Zone (腾讯专区) | 17 | Marketing Growth (营销增长) | 29 |
| Product Design (产品设计) | 17 | Content Creative (内容创作) | 27 |
| Engineering (技术工程) | 29 | Sales Commerce (销售商务) | 10 |
| Finance Investment (金融投资) | 23 | Operations HR (运营人力) | 6 |
| Game & Spatial (游戏空间) | 24 | Project Quality (项目质量) | 23 |
| Data & AI (数据智能) | 20 | Security Compliance (法务安全) | 14 |
| Industry Consultant (行业顾问) | 7 | **Total** | **246** |

Full clickable index at [`experts/INDEX.md`](experts/INDEX.md); structured fields (tags / quickPrompts / defaultInitPrompt / avatar) at [`experts/manifest.json`](experts/manifest.json).

### 4. [`PROMPTS.md`](PROMPTS.md) — full reverse-engineering report

Covers: client architecture, IPC channel list, expert marketplace COS paths, ranking API, client cache locations, reproduction steps, and risk boundaries. The report itself is in Chinese.

---

## How to use

```bash
# 1. Browse all experts (categorized + relative links)
open experts/INDEX.md

# 2. Inspect manifest fields of one expert (tags / quickPrompts / default init prompt)
jq '.experts[] | select(.id=="UIDesigner")' experts/manifest.json

# 3. Read one expert's prompt body
cat experts/prompts/plugins/ui-designer/agents/ui-designer.md

# 4. Study the template composition mechanism
less templates/workbuddy-prompt.tpl
less templates/workbuddy-expert-prompt.tpl  # see where Role Override is injected

# 5. Track upstream changes (manifest's lastUpdated field)
curl -s https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/expert_center.json | jq '.lastUpdated'
```

---

## Technical quick reference

| Item | Value / Path |
|---|---|
| Prompt override mechanism | Line 36 of `workbuddy-expert-prompt.tpl`, Role Override clause |
| Client data directory | `~/.workbuddy/` (contains `workbuddy.db`, expert cache, etc.) |
| MCP config file | `~/.workbuddy/mcp.json` |
| Expert marketplace COS base | `https://acc-1258344699.cos.accelerate.myqcloud.com/workbuddy/expert-marketplace/` |
| Ranking API | `/console/expert/ranking` (requires login — **not provided in this repo**) |
| Manifest path | `/expert_center.json` (public anonymous access) |
| Client cache | `~/.workbuddy/app/cache/experts/manifest.json` |

---

## Reproducing the `asar/` directory

`asar/` is the full unpack of WorkBuddy's `app.asar` (~495 MB, includes node_modules and renderer chunks). It is not stored in git. To reproduce:

1. Install [WorkBuddy](https://copilot.tencent.com/) 4.22.16 (or an equivalent version)
2. Run `npx asar extract /Applications/WorkBuddy.app/Contents/Resources/app.asar ./asar/`
3. See [`PROMPTS.md`](PROMPTS.md) §1 and §5 for detailed paths and key code locations

---

## Related resources

- Upstream prompt source project: [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents) (MIT)
- WorkBuddy official: [copilot.tencent.com](https://copilot.tencent.com/)
- Full reverse-engineering report: [`PROMPTS.md`](PROMPTS.md) (Chinese)
- Legal boundaries: [`LICENSE`](LICENSE) / [`NOTICE`](NOTICE)

---

## License

The curation, index, and report parts are released under **MIT**. Expert prompt bodies and WorkBuddy templates remain copyrighted by upstream authors and Tencent. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) for details.
