# TASKBOARD — 可选 V12 用户壳（非 P0）

> 触发条件：业务要求「终端用户交互接近腾讯 WorkBuddy 桌面」。  
> **当前主线多租户交付不依赖本板。**  
> 对照：`deploy/enterprise/WORKBUDDY_PARITY_AUDIT.md`

## Done 标准（仅当启动时）

1. Web 三栏：任务侧栏 / 对话中栏 / 结果右栏（产物·文件·变更·预览）
2. 100% 复用 `task` / `goal` / `runtime` / JWT；不重写引擎
3. 登录 = 现有 tenant JWT 或 Casdoor 换发
4. 仍不：Electron、计费、小程序、fork Octop Dashboard 全量

## 拆解（未启动）

| ID | 交付物 | 状态 |
|---|---|---|
| V12.1 | 任务侧栏：列表/新建/搜索/筛选 | ⬜ |
| V12.2 | 对话中栏：消息/追问/中断/模式 Ask·Plan·Craft | ⬜ |
| V12.3 | 结果右栏四 Tab | ⬜ |
| V12.4 | Skills 安装 UI（调现有 market API） | ⬜ |
| V12.5 | 验收剧本 vs 腾讯入门指南章节映射 | ⬜ |
