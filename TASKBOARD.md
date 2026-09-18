# TASKBOARD — 项目空间 + 专家技能闭环

> 最重要一环：项目空间挂技能，任务执行自动加载。

## Done

1. 租户级 `projects/` 根 + `/api/projects*` CRUD/详情/技能列表  
2. `skills/deposit`：从技能市场存入项目空间  
3. `run_task` 按 `task.project_id` 绑定项目 skills + 注入项目 MEMORY  
4. shell：项目选择器 / 新建 / 项目面板 / 「存入项目」  
5. 修复 LiveStepRunner 内容截断（嵌套全角括号）  
6. `verify_project_space.py` 通过  

| ID | 状态 |
|---|---|
| PS.1 项目 API + 租户路径 | ✅ |
| PS.2 run_task 绑定技能 | ✅ |
| PS.3 shell 项目 UX | ✅ |
| PS.4 verify + 重启实测 | ✅ |

## 验收

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -S scripts\verify_project_space.py
python -S scripts\verify_v17.py
```

## 距主线

- 流式 SSE（可选）  
- Harbor sec-full Windows 样本限制  
- 项目成员协作 / 权限细化（当前租户共享 projects）
