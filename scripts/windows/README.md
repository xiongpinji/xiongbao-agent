# Windows Scheduled Task — Routine `tick`

每分钟调用 Teach/Routine 调度器，无需常驻 Python 进程。

## 一键注册（当前用户）

在仓库根目录以 **普通用户** PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\register_routine_tick.ps1
```

默认：

| 项 | 值 |
|---|---|
| 任务名 | `XiongbaoAgent-RoutineTick` |
| 周期 | 每 1 分钟 |
| 工作目录 | 仓库根 |
| 模式 | `dry`（安全默认；上线改 `-Mode live`） |
| Root | `artifacts\teach_routine` |

## 参数

```powershell
# 试跑 live + 指定 root
powershell -File scripts\windows\register_routine_tick.ps1 -Mode live -Root artifacts\teach_routine

# 自定义任务名 / Python
powershell -File scripts\windows\register_routine_tick.ps1 -TaskName "MyTick" -PythonExe "C:\Python312\python.exe"
```

## 卸载

```powershell
powershell -File scripts\windows\unregister_routine_tick.ps1
# 或
Unregister-ScheduledTask -TaskName "XiongbaoAgent-RoutineTick" -Confirm:$false
```

## 手动等价命令

```powershell
cd "<repo>"
$env:PYTHONPATH = (Get-Location).Path
python -S -m octop.contrib.workbuddy.teach_cli --root artifacts\teach_routine tick --mode dry
```

## 注意

- `live` 模式仍受 Routine 审批与 `WB_ALLOW_OUTBOUND` 门禁约束
- 笔记本合盖休眠时任务可能漏跑；服务器/常开机更合适
- 管理员权限：当前脚本用当前用户注册，一般不需要提权
