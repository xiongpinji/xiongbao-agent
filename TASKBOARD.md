# TASKBOARD — V14 环境联调与 Office / Harbor live

> 已完成。

## Done

1. casdoor(+mysql) / milvus profile 拉起；`/api/enterprise` configured+reachable  
2. docx/xlsx 文本预览  
3. `POST /api/harbor/score`（默认 dry）  
4. `verify_v14.py` OK；Hub v=14

| ID | 状态 |
|---|---|
| V14.1 企业 profile 联调 | ✅ |
| V14.2 Office 预览 | ✅ |
| V14.3 Harbor score | ✅ |
| V14.4 verify + commit | ✅ |

## 可选后续

- Casdoor 完整 OIDC 换发联调（需在 Casdoor 控制台建应用/用户 claims）  
- Harbor `live=1` 全量评分（耗时长）  
- pptx 预览
