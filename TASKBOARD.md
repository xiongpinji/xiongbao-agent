# TASKBOARD — V17 四维质量提升（功能/交互/结构/视觉）

> shell.html 产品壳收口；不引入 React。

## Done

1. C1–C2：抽出 `tokens.css` / `shell.css`；顶栏单行 +「更多」菜单  
2. D1+D5：登录品牌卡（API Key / Casdoor）+「仅演练」开关  
3. A1–A3+B5/B6：人话映射、默认真执行、状态轮询、中文角色/芯片  
4. B1–B4/B7–B8：loading/toast/空态 CTA/窄屏三段/Enter/徽章  
5. A4–A7：SSO 页签、模型 chip、下载、任务改名删除  
6. D2–D4+C3–C5：气泡/侧栏/右栏/布局档位；运维降权到设置/更多  
7. `verify_v17` + 审计分数刷新

| ID | 状态 |
|---|---|
| V17.C 结构抽出+顶栏 | ✅ |
| V17.D 登录/发送视觉 | ✅ |
| V17.A 人话+真执行+状态机 | ✅ |
| V17.B 交互收口 | ✅ |
| V17.A4–7 SSO/模型/下载/CRUD | ✅ |
| V17.D 打磨+布局档位 | ✅ |
| V17.verify | ✅ |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v17.py
```

## 距主线

- 流式 SSE（可选 V18）  
- Harbor sec-full Windows 样本题（平台限制，非用户壳门禁）  
- 公网 Let's Encrypt（本地 tls internal 已够私有化）
