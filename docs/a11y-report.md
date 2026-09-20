# 无障碍（a11y）报告 — WorkBuddy Console

**审计工具：** 自写 Playwright + DOM 检查（`octop/contrib/workbuddy/console/e2e/run-a11y.mjs`）。
**审计范围：** `index.html`、`shell.html`、`ops.html` 三页。
**审计时间：** 报告生成时即仓库 HEAD。
**目的：** 把 a11y 当作 ship bar 的一部分，跟踪回归。

## 1. 检查项

| 检查 | 实现方式 |
| --- | --- |
| `<html lang>` 存在 | `document.documentElement.lang` |
| `<title>` 非空 | `document.title` |
| viewport meta | `meta[name="viewport"]` 选择器 |
| 是否有标题（h1/h2 或 role=heading） | DOM 选择 |
| `<img>` 全部有 `alt` | 遍历 `img`，断言 `alt !== null` |
| 表单控件有可访问名 | `label[for=...]` / `aria-label` / `aria-labelledby` 之一 |
| 可聚焦元素 ≥ 1 | `a[href]`、`button`、`[tabindex]:not(-1)` |
| Tab 顺序 + 焦点可见 | 前 8 个可聚焦元素逐个 `Tab`，断言 `offsetParent !== null` |
| 主体字号 | `getComputedStyle(body).fontSize` |

## 2. 当前结果（HEAD）

```
index.html  zh-CN  bodyFontPx=16  images=0  interactive=12  controls=3
shell.html  zh-CN  bodyFontPx=13  images=5  interactive=93  controls=7
ops.html    zh-CN  bodyFontPx=14  images=1  interactive=16  controls=3
```

整体：
- 三页 lang / title / viewport / h1 全部合规。
- shell 主体字号 **13px**，低于项目内部约定的 ≥14px（DESIGN.md 基础字号 14）。
- 表单输入可访问名普遍缺失（详见下表）。

## 3. 违规清单

### 3.1 表单控件无可访问名（13 条）

| 页面 | 元素 | 现状 | 建议 |
| --- | --- | --- | --- |
| index | `<input id="tid" autocomplete="username">` | placeholder 仅有 | 加 `<label for="tid">` 或 `aria-label="租户"` |
| index | `<input id="uid" value="admin">` | 仅 value | 同上 |
| index | `<input id="akey" type="password">` | 无 | 同上 |
| shell | `<input id="fileInput" type="file" hidden>` | hidden，AT 不可达 | 移除 hidden + 加 label，或 `aria-hidden="true"` 显式跳过 |
| shell | `<input id="dryRun" type="checkbox">` | 缺 label | 显式 `<label for="dryRun">试运行</label>` |
| shell | `<input id="rightSearch" type="search">` | 仅有 placeholder | 加 `aria-label="搜索"` |
| shell | `<input name="tid" required>` | 仅 placeholder | 加 `aria-label` |
| shell | `<input name="uid" required>` | 同上 | 同上 |
| shell | `<input name="key" type="password" required>` | 同上 | 同上 |
| shell | `<textarea name="casdoor" required>` | placeholder 长串 | 加 `aria-label="Casdoor Token"` |
| ops | `<input id="tid">` | 缺 label | 同 index |
| ops | `<input id="uid">` | 缺 label | 同上 |
| ops | `<input id="akey">` | 缺 label | 同上 |

### 3.2 其它

| 页面 | 问题 | 严重度 |
| --- | --- | --- |
| index | 焦点落在 `<body>` 时 `offsetParent === null`（可能 layout 边界场景） | 低（仅在 `focusable <= 1` 时偶发） |
| shell | 主体字号 13px | 中（DESIGN.md 要求 ≥14） |

## 4. 修复优先级

| 优先级 | 项目 | 影响 |
| --- | --- | --- |
| **高** | shell 主体字号提到 14px | 影响全部文字可读性 |
| **高** | shell login 表单 3 个输入加 label/aria-label | 屏幕阅读器 / 键盘导航 |
| **中** | index / ops 登录表单 3 个输入加 label | 同上 |
| **中** | shell 文件上传 `<input type="file" hidden>` 改造 | 当前 hidden 对键盘用户也隐藏 |
| **低** | shell `dryRun` checkbox 加 label | 单点 |

## 5. 持续监督

`run-a11y.mjs` 与 `run-smoke.mjs` 共用同一套 Playwright 静态服务器，可合并为 CI
单步：

```bash
node octop/contrib/workbuddy/console/e2e/run-smoke.mjs && \
node octop/contrib/workbuddy/console/e2e/run-a11y.mjs
```

修掉所有「高 / 中」项之前，`run-a11y.mjs` 退出码非 0，会在 CI 失败。

## 6. 已知未覆盖项

- **颜色对比度**：未做像素级检测。Console 的 `tokens.css` 是
  WorkBuddy 品牌色板，由设计侧确认满足 WCAG AA。
- **键盘焦点环样式**：未断言 `outline-width >= 2px` 或 `box-shadow` 焦点环存在，
  后续可补一项。
- **RongXinAI Desktop 主窗口**：Electron 端由 Vitest 覆盖组件行为，未做 a11y
  DOM 检查。Electron 的可访问性走 Chromium DevTools，可加 `--enable-features=AccessibilityAriaVirtualContent`
  在 `e2e:electron` 中跑 axe-core。

## 7. 复现

```bash
node octop/contrib/workbuddy/console/e2e/run-a11y.mjs
```

退出码 `0` = 全绿，`1` = 仍有违规。脚本末尾打印每页摘要与违规列表，便于直接复制粘贴到 issue。
