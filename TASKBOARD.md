# TASKBOARD — V12 差距补齐（用户壳 + 残留能力）

> 基线：V1–V11 + Go-Live P0 已交付。  
> 本板目标：按审计 **补齐交互 / 前端 / UI 主差距**。  
> **边界**：不复刻 Electron / 计费 / 小程序。

## Done 标准 — 已满足

1. Web 三栏壳：`/` → `shell.html`；运维 `/ops.html`
2. 新建 → 发消息 → dry-run → 右栏结果
3. Skills 壳内安装
4. `verify_v12.py` 全绿；Hub `v=12`

## 任务拆解

| ID | 交付物 | 状态 |
|---|---|---|
| V12.0 | 看板 + ROADMAP | ✅ |
| V12.1 | Task API create/get/message/patch + pin/archive/search | ✅ |
| V12.2 | Workspace API artifacts/files/changes/preview | ✅ |
| V12.3 | Skills install API | ✅ |
| V12.4 | `shell.html` 三栏 UI | ✅ |
| V12.5 | `/` shell + `/ops.html` 运维 | ✅ |
| V12.6 | Hub v12 + `verify_v12.py` | ✅ |
| V12.7 | PARITY_AUDIT 评分更新 + commit | ✅ |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_v12.py
# → VERIFY V12 OK
```

## 残留（可选下一板）

- 附件上传 / Office 富预览
- Casdoor·Milvus 凭据实连
- Harbor 全量 live
