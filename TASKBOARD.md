# TASKBOARD — V13 残留补齐（上传 / 富预览 / 企业状态 / Harbor）

> 基线：V12 三栏壳已交付。本板已完成。

## Done 标准 — 已满足

1. 附件上传 → `attachments/` + 右栏可见  
2. HTML iframe / Markdown / 图片预览  
3. `/api/enterprise` + 壳内 SSO/向量芯片  
4. `POST /api/harbor/dry-run`（壳顶栏 + 运维台）  
5. `verify_v13.py` → `VERIFY V13 OK`；Hub `v=13`

| ID | 状态 |
|---|---|
| V13.1 Upload API + 壳内上传 | ✅ |
| V13.2 富预览 | ✅ |
| V13.3 Enterprise 状态面 | ✅ |
| V13.4 Harbor dry-run | ✅ |
| V13.5 Hub/verify/docs | ✅ |

## 仍可选（环境依赖）

- Casdoor/Milvus **填真实凭据**后可达探测变绿  
- Harbor **全量 live** 评分（非门禁）  
- Office 在线渲染（docx/xlsx）
