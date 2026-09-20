# 熊宝 Agent 端到端交付指南

本指南面向**交付实施者**：在 Windows 本机把 Octop 后端 × 桌面 × 移动 PWA 三段打通，并产出三件交付物。

## 1. 交付物清单（dist/）

| 文件 | 大小 | 来源 | 说明 |
|---|---|---|---|
| `octop-1.0.0-py3-none-any.whl` | ~9.7 MB | `cd octop && uv build` | Octop 后端 Python wheel |
| `install-octop.bat` | ~8 KB | `scripts/install-octop.bat` | 一键安装后端（uv + venv + wheel） |
| `mobile-dist.zip` | ~120 KB | `npm run build` 后压 | PWA 静态资源 |
| `熊宝Agent-Setup-<version>.exe` | 视打包 | `cd vendor/RongXinAI && npm run dist:win` | NSIS 安装包 |

> **NSIS 打包前置**：本机需先安装 [Bun](https://bun.sh)（`packageManager: "bun@1.4.0"`）。`dist:win` 会下载 channel runtime、engram runtime、llama.cpp 等附加资源，**首次运行需要 ~30-60 分钟**。

## 2. 安装顺序

### 2.1 安装 Octop 后端

```powershell
# 1. 解压交付包到任意目录
# 2. 在该目录打开管理员 PowerShell
# 3. 安装后端（默认装到 %USERPROFILE%\.octop）
.\install-octop.bat

# 4. 启动
%USERPROFILE%\.octop\venv\Scripts\octop.exe run

# 5. 打开 http://127.0.0.1:8088
```

如果系统无 Python 3.12+：

```powershell
.\install-octop.bat --portable
# 自动下载 portable Python 3.13 解压到 %USERPROFILE%\.octop\python
```

### 2.2 安装桌面端

双击 `熊宝Agent-Setup-<version>.exe` 走 NSIS 引导：
1. 选择安装目录（默认 `C:\Program Files\熊宝Agent`）
2. 选择「创建桌面快捷方式」/「开始菜单项」
3. 等待 channel runtime + engram runtime 解压
4. 安装完成后首次启动会引导「配置 Octop 连接」

打开桌面端 → 设置 → **Octop 连接**：
- 服务地址：`http://127.0.0.1:8088`
- 账号 / 密码：当初 `octop init` 创建的 admin
- Agent ID：上一步 `/api/agents` 列表里的 ID
- 启用 Octop 接管 IM：**开**（默认）

### 2.3 部署 PWA

把 `mobile-dist.zip` 解压到任意静态托管目录，例如：

```powershell
# 用 IIS / nginx / caddy 都能托管
# 例：放到 octop 自带的 static mount（若已挂载）
Expand-Archive mobile-dist.zip -DestinationPath C:\inetpub\wwwroot\xiongbao-mobile
```

或者直接双击 `index.html` 在本地浏览器打开（Chrome 会提示 PWA install）。

手机访问：`http://<电脑 IP>:8088/mobile/`，登录同一个账号 → 同一 agent。

## 3. 验证（deliver_smoke）

```powershell
cd <xiongbao-agent-root>
python -S scripts/deliver_smoke.py --password <admin-pwd> --timeout 30
```

期望输出：

```
[1/7] Octop 后端 /api/health               PASS
[2/7] /api/auth/login 返回 JWT             PASS
[3/7] 至少 1 个 agent 存在                  PASS
[4/7] WS /api/agents/{id}/chat/ws 出答      PASS
[5/7] mobile/ npm test 通过                PASS
[6/7] dist/mobile-dist.zip 存在             PASS
[7/7] dist/octop-*.whl + install-octop.bat PASS

  Total: 7  Passed: 7  Failed: 0  Skipped: 0
```

注意：
- 必须在 `python -S`（跳 site 模块）下运行，否则 Windows 上中文路径会触发 `gbk` 编码错误。
- 第 4 项需要 admin 已经创建过至少一个 agent，否则先通过 Dashboard 或 `POST /api/agents/` 建一个。
- 第 4 项需要 provider 已配置（带 API key），否则 LLM 会 401/402。

## 4. 故障排查

| 现象 | 原因 | 解决 |
|---|---|---|
| `install-octop.bat` 报 `Failed to install uv` | 网络/防病毒拦截 | 手动装 uv：https://astral.sh/uv |
| `python -S scripts/deliver_smoke.py` 报 `gbk` 解码错误 | 中文路径 + Python <3.13 site 加载 | 必须 `-S` 跳 site；或换 Python 3.13 |
| `npm run dist:win` 报 `bun: command not found` | 未装 Bun | `irm https://bun.sh/install.ps1 \| iex` |
| WS smoke 显示 `closed after 0 chunks` | 后端没起来 / agent 不存在 / API key 无效 | curl `/api/health` 和 `/api/agents` 确认 |
| 桌面端「Octop 连接」点登录返回 `无法连接 Octop 后端` | 桌面端 / 后端不在同一台机器 | 在「服务地址」填入 `http://<后端 IP>:8088`，并放通 8088 防火墙 |
| `GET /api/providers` 返回含 `api_key` 明文 | Octop 路由已知行为 | 仅 admin 角色可见；建议通过 OAuth/proxy 鉴权后再外暴 |

## 5. IM 真渠道（Phase D，可选）

当前 `OctopChatHandler` 是默认 IM 后端。`OctopChatClient` 已能正确解析 server 的 `token` / `chunk` / `done` 帧。

如需启用钉钉/企微/飞书：

1. 拿到渠道的 AppID/Secret 或 Webhook+Secret
2. 桌面端 → 设置 → IM → 对应渠道填入
3. 重启桌面端，IM gateway 会自动绑定
4. 手机发消息 → Desktop 入站 → Octop → DeepSeek → 回发

`use_octop_for_im` 关闭后会回退到旧的「直接对 LLM provider」路径（兼容性保留）。

## 6. 验收口径

走完 1-3 节后必须满足（plan §8）：

1. ✅ 双击 `熊宝Agent-Setup-*.exe` 安装 → 双击打开 → 设置页连到本机 Octop → cowork session 收到真 LLM 流式回答
2. ⏸ 手机钉钉/企微/飞书发一句话 → Desktop 上看到入站消息 + 出站回复（**需要 IM 凭证**，plan 默认挂起）
3. ✅ 同 WiFi 手机浏览器访问 `http://<电脑IP>:8088/mobile/` → 登录 → 同一 agent 跑通
4. ✅ `python -S scripts/deliver_smoke.py` 输出 7/7 PASS

## 7. 已知遗留（不阻塞交付）

- NSIS 完整打包（`dist:win`）首次执行需要下载多个 runtime 子包，离线环境需要提前预热。
- `GET /api/providers` 当前返回明文 `api_key`（**仅 admin 角色可见**），建议下一迭代在 schema 中改 `api_key: "***"`。
- `OctopChatHandler` 用 harness 自有 token 协议（`type: "token"`）而非老 dashboard 的 `chunk`，已在 desktop `OctopChatClient` 中兼容，但其他 IM 网关如自定义可能需要同步适配。
