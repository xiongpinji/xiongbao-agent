# 安全审计报告 — Skill 沙箱 / preload 白名单

**审计范围：** Octop 后端的 Skill 脚本沙箱、RongXinAI Desktop 的 Electron preload 白名单。
**审计人：** 自动化 + 人工抽样。
**审计版次：** 对应 `xiongbao-agent` 当前 HEAD。
**结论：** 现有防御覆盖核心攻击面；以下条目建议跟进。

---

## 1. Skill 脚本沙箱（`octop/contrib/workbuddy/skills/sandbox.py`）

### 1.1 已实现的护栏

| 护栏 | 实现 | 测试覆盖 |
| --- | --- | --- |
| 脚本路径必须在 `scripts/` 下 | `resolve_script()` 用 `target.relative_to(scripts_root)` 校验 | `test_resolve_script_rejects_path_traversal` ✅ |
| `..` / 绝对路径拒绝 | `if ".." in Path(rel).parts` | `test_resolve_script_rejects_path_traversal` ✅ |
| 仅白名单后缀可执行 | `ALLOWED_SUFFIXES = {.py, .js, .mjs, .ts, .sh, .ps1, .bash}` | `test_list_skill_scripts_returns_only_allowed_suffixes` ✅<br/>`test_resolve_script_rejects_disallowed_extension` ✅<br/>`test_run_skill_script_blocked_for_disallowed_suffix` ✅ |
| `subprocess` argv 列表 | `subprocess.run(argv, ..., shell=False)` | 由代码 review 确认 ✅ |
| 超时 | `subprocess.run(..., timeout=timeout_s)` | `test_run_skill_script_timeout`（Windows 跳过）✅ |
| 输出截断 | `max_output_chars` | `test_run_skill_script_caps_output` ✅ |
| `allow_net=False` 剥离代理 | 显式 `pop` 6 个代理环境变量 + 设 `NO_NETWORK=1` | `test_run_skill_script_strips_proxy_env_when_no_net` ✅ |
| 错误结构化返回 | `run_skill_script` 捕获 `ScriptSandboxError`，返回 `ScriptRunResult(ok=False)` | `test_run_skill_script_returns_failure_on_traversal` ✅ |

测试文件：`octop/tests/unit/contrib/workbuddy/test_skill_sandbox.py`，14 通过 + 1 Windows 跳过。

### 1.2 已知限制 / 改进建议

1. **Python 解释器共享主进程 site-packages**
   `python -S <script>` 不加载 site，但解释器本身仍能 `import os` / `subprocess`。
   在共享主机或被植入恶意 Skill 的场景下，Skill 脚本仍可调用 `subprocess.Popen` 启动外部进程。
   建议：未来版本切换到 `bwrap` 或 `docker run --network=none --read-only`（项目已有
   `infra/backend/opensandbox_deps.py` 钩子，但目前仅用于 backend 存储，尚未覆盖 skill）。
   优先级：**中**（信任模型依赖 Skill 来源，市场 / Hub 的 Skill 在落地前应有审计）。

2. **`env_extra` 可绕过代理剥离**
   `run_skill_script()` 先 `pop` 代理再 `env.update(env_extra)`。如果调用方在
   `env_extra` 里塞 `HTTP_PROXY`，沙箱会重新把它写回去——这是一个真实的「特权升级」路径。
   建议：`allow_net=False` 时显式拒绝任何 `env_extra` 中的代理类键。
   优先级：**高**（已在测试注释中标记，详见 `_load_sandbox` 注释）。

3. **超时粒度仅到秒**
   Windows 下 `subprocess.run(timeout=)` 使用 `WaitForSingleObject`，短超时（如 0.1s）
   容易假阳/假阴。脚本提供 `timeout_s=0.5` 但没保证在所有平台都按预期工作。
   测试已用 `pytest.skip` 跳过该路径。
   优先级：**低**。

4. **未做磁盘 / 内存配额**
   脚本可以写满磁盘或无限内存。OS-level cgroup / quota 是最终方案，
   但需要部署侧 systemd unit 配合 `MemoryMax=` / `TasksMax=`。
   优先级：**低**（依赖部署）。

---

## 2. RongXinAI Desktop preload 白名单

### 2.1 防护设计

`vendor/RongXinAI/src/main/preload.ts` 通过 `contextBridge.exposeInMainWorld`
仅暴露一组具名 IPC 通道。每个通道名是一个常量（参见
`vendor/RongXinAI/src/shared/ipc/channels.ts`），分散在 `AppIpc` /
`CoworkSessionIpc` / `McpIpc` / … 等命名空间下。

| 防御层 | 位置 | 状态 |
| --- | --- | --- |
| `contextIsolation: true` | `BrowserWindow` 配置 | ✅（AGENTS.md §Security 要求） |
| `nodeIntegration: false` | 同上 | ✅ |
| `sandbox: true` | 同上 | ✅ |
| `contextBridge.exposeInMainWorld` 显式命名 | `preload.ts` | ✅ |
| 所有 IPC 名字都是常量 | `shared/ipc/channels.ts` + 各模块 `constants.ts` | ✅（`AGENTS.md §String Literal Constants` 强制） |
| `ipcMain.handle()` 与 `ipcRenderer.invoke()` 配对 | `src/main/ipcHandlers/*.ts` | ✅（人工抽样确认） |

### 2.2 已知限制

1. **暴露面仍然较宽**
   `preload.ts` 第 12–45 行一次性导入约 30 个 IPC 命名空间。任意一个被攻陷的 handler
   都会成为 RCE 入口。建议：按页面或按权限拆分 expose，按页面 import 而不是总入口。
   优先级：**中**。

2. **未做 IPC handler 侧的入参 schema 校验**
   受 AGENTS.md 推行的 Pydantic 等价校验尚未在所有 `ipcMain.handle()` 中落地。
   `api/routers/` 用了 Pydantic 模型，但 `src/main/ipcHandlers/` 部分 handler 仍
   接 `any`。建议：把所有 handler 入参用 zod / 自写校验器封一层。
   优先级：**中**。

3. **`SkillSecurityScannerMerge` 路径未在 preload 内暴露**
   Skill 加载走主进程 IPC，renderer 不能直接调用 Skill 脚本——这是正确的隔离。
   但这意味着 Skill 漏洞等同于主进程 RCE，Skill 侧需要更严格的输入消毒（见 §1）。

---

## 3. 测试覆盖总结

| 模块 | 测试文件 | 通过 |
| --- | --- | --- |
| Skill 沙箱 | `octop/tests/unit/contrib/workbuddy/test_skill_sandbox.py` | 14/14 + 1 skip |
| Preload 通道常量 | `vendor/RongXinAI/tests/electron-builder-hooks.test.ts` 等 | 见 `npm test` |
| Skill frontmatter 审计 | `vendor/RongXinAI/tests/skillFrontmatter.test.mjs` 等 | 见 `npm test` |
| Skill 安全扫描合并 | `vendor/RongXinAI/tests/skillSecurityScannerMerge.test.mjs` | 见 `npm test` |
| Skill 安全规则 | `vendor/RongXinAI/tests/skillSecurityRules.test.mjs` | 见 `npm test` |

## 4. 建议的下一步

1. 在 Skill 沙箱里增加 `env_extra` 键过滤（见 §1.2 #2，**高优**）。
2. 为 `ipcMain.handle()` 入参写 zod schema，并扩展 `tests/unit/ipcHandlers/` 覆盖。
3. 在 `preload.ts` 内按命名空间延迟 expose，按页面 export 减少 renderer 攻击面。
4. 后续 P2-8 a11y / P3-x 商用打磨阶段，对 Skill 引入 `bwrap` 后端；当前实现适合
   「用户自己安装的 Skill」，不适合「开放市场 Skill」。
