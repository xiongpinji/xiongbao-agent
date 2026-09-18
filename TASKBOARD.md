# TASKBOARD — 多租户生产硬化（V11）

> 基线：V1–V10 已交付（能力对齐 + 运行时贯通）。  
> 本板目标：**一套实例服务多家客户（多租户）**，可私有化部署、可验收隔离。  
> **边界**：不复刻腾讯云 SaaS 计费/小程序；租户模型落在 WorkBuddy 层 + Octop 多用户映射，不改 Octop 核心 Dashboard。

## 部署定义（Done 标准）

1. 两租户数据互不可见（artifacts / Console API / Milvus 命名空间）
2. Console 鉴权开启，管理面不对未授权网络裸奔
3. Compose 可私有化拉起（IP / 内网 / localhost 均可；**域名非交付标准**）
4. 租户可注册、配额可强制、可按租户备份/恢复
5. `verify_v11.py` 全绿

## V11 任务拆解

| ID | 交付物 | 验收 | 状态 |
|---|---|---|---|
| V11.1 | `tenant/`：Tenant 注册表 + JWT claims(`tid`/`uid`) | 创建两租户；签发/校验 token | ✅ |
| V11.2 | `TenantRoots`：`artifacts/tenants/<tid>/users/<uid>/…` | 跨租户路径不重叠 | ✅ |
| V11.3 | Console 强制鉴权 + 本租户 Task 列表 | 无 token→401；跨租户不泄漏 | ✅ |
| V11.4 | 租户配额（tasks/storage_mb/agents） | 超限明确错误 | ✅ |
| V11.5 | `tenant backup/restore` 切片 | 只动本租户数据 | ✅ |
| V11.6 | Milvus collection=`wb_{tid}` 前缀 | 跨租户 search 不串 | ✅ |
| V11.7 | Casdoor token → Console 会话桥（可选） | 配置后可换发本系统 JWT | ✅ |
| V11.8 | 生产 Compose：Caddy + TLS 样例 + 隐藏 8010 | 文档一键起 | ✅ |
| V11.9 | `deploy/enterprise/MULTI_TENANT.md` runbook | 目录树/权限/运维 | ✅ |
| V11.10 | Hub v11 + `verify_v11` + 单测 + docs | VERIFY V11 OK | ✅ |

## 明确不进 V11

- 腾讯闭源 Electron / 云计费 / 小程序
- 修改 Octop Dashboard React
- Harbor 真机全量评分（仍 dry/harness）
- 完整计费账单系统（仅留配额钩子）

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v11.py
# → VERIFY V11 OK
```
