# 数据迁移回滚（octop 0.x → 1.x）

> **TL;DR**：所有回滚都遵循 **「先备份，再操作，绝不在 `octop run` 在线时改 DB」**。
> 默认路径是 `octop backup restore`；只有当 `backup restore` 不可行时再用
> `scripts/db_downgrade.py`。

## 1. 支持的回滚路径

| 场景 | 推荐路径 |
| --- | --- |
| 升级到 v0.20+ 后发现 bug，需要回到 v0.19 | `octop backup restore <v0.19 的 archive>` |
| 升级后发现 **schema-only** 破坏（数据完好） | `scripts/db_downgrade.py --target N` |
| 从 v1.0 回到 v0.x（cross-major） | `octop backup restore`（不支持跨大版本 SQL 兼容） |
| Postgres 实例 | `pg_dump` 备份 + 在旧实例上 `pg_restore` |

脚本当前覆盖的回滚区间：**v16 → v12**（drop plan 写明）。

## 2. `octop backup restore`（首选）

```bash
# 1. 停止 octop
octop service stop   # 或 systemctl / tasklist + kill

# 2. 列出可用备份
ls ~/.octop/backups/

# 3. 还原
octop backup restore ~/.octop/backups/octop-backup-20260101T120000Z.tar.gz \
  --yes

# 4. 用旧二进制启动
~/.local/bin/octop-v0.19.7 run
```

`restore` 会自动执行 `run_migrations`，如果 manifest.schema_version > 旧二进制的
最大版本号，会抛 `BACKUP_SCHEMA_INCOMPATIBLE`。这是预期的：跨大版本不能用
SQLite 文件拷贝回滚。

## 3. `scripts/db_downgrade.py`（schema-only）

适用于：

- 你升级了 `pip install octop --upgrade`，但 **没有**提前备份；
- 新版本新增的表是「附加」（不影响旧逻辑）；
- 旧二进制不会主动 SELECT 那些新表。

### 3.1 用法

```bash
python scripts/db_downgrade.py --target 15            # 询问确认
python scripts/db_downgrade.py --target 15 --yes      # 跳过确认
python scripts/db_downgrade.py --target 15 --backup   # 先做 .bak
python scripts/db_downgrade.py --target 15 \
  --force-data-loss    # 新表里有数据也强行 DROP（数据丢失）
```

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功或 no-op |
| `2` | 新表里有数据，需要 `--force-data-loss` 或改用 `backup restore` |
| `3` | 当前 driver 是 Postgres（请用 `pg_dump`） |
| `4` | 找不到 `~/.octop/db/octop.db` |
| `5` | `_schema_version` 不存在 |
| `6` | `--target` < 1 |
| `7` | `_schema_version` ≥ 当前已知最大版本（无 drop plan） |

### 3.2 内置 drop plan

| 版本 | 动作 |
| --- | --- |
| 16 | drop `credit_account`、`credit_ledger`、相关索引 |
| 15 | drop `agent_acl`、相关索引；**恢复** `agents.is_shared` 列（v15 之前的旧 binary 需要） |
| 14 | drop `user_policies` |
| 12 | drop `trajectory_events`、相关索引 |
| 13 | drop plan **暂未提供** — v13 把 `connectors` 重命名后重建，仅靠 SQLite 无法安全逆向；请用 `backup restore` |

### 3.3 实战示例

```text
$ python scripts/db_downgrade.py --target 15 --yes --backup
[db-downgrade] backup written to /home/me/.octop/db/octop.db.bak
[db-downgrade] v16: dropping credit_account / credit_ledger (v16)
[db-downgrade] _schema_version clamped to 15
[db-downgrade] done. Restart `octop run` with the older binary.
```

之后用旧 binary：

```bash
octop --version    # 0.19.x
octop run
```

## 4. 已知不会写进 drop plan 的内容

- **新增列**（`_ensure_*_schema` 类 helper 补的列）— SQLite `DROP COLUMN` 是
  3.35+ 才支持，旧 binary 看到多余列通常无害（不 SELECT 即可）。如果旧 binary
  用 `INSERT INTO table (col_a, col_b)` 显式列名，**多余列不会写坏数据**。
- **新增索引** — 多余的索引在旧 binary 上是透明的，无需回滚。
- **视图** — `_ensure_*_schema` 创建的视图如果旧 binary 不引用，drop 不是必要。
- **PostgreSQL-only 扩展** — 永远不会被脚本处理。

## 5. 强制数据丢失语义

`--force-data-loss` 会让脚本在以下情况仍然继续：

- `credit_account` 有余额
- `credit_ledger` 有交易
- `agent_acl` 有授权
- `user_policies` 有策略

**先备份再 --force-data-loss**。否则一旦执行，**这些行无法恢复**。

```bash
python scripts/db_downgrade.py --target 13 --yes --backup --force-data-loss
cp ~/.octop/db/octop.db.bak /safe/location/
```

## 6. 自检

每个 downgrade 完成之后，建议执行：

```bash
sqlite3 ~/.octop/db/octop.db "SELECT version FROM _schema_version;"
sqlite3 ~/.octop/db/octop.db ".tables" | grep -E "credit|agent_acl|user_policies"
# 期望：第一个命令打印 13；第二个命令无任何输出
```

## 7. CI / 烟雾测试

`tests/unit/scripts/test_db_downgrade.py` 覆盖：

- v16 → v15：drop `credit_*` 表
- v16 → v13：drop v15 + v14 + v16，且 v15 的 side-effect 恢复 `is_shared`
- 幂等：相同 target 第二次返回 no-op
- target ≥ current：no-op
- 默认拒绝有数据的表
- target 跨过未知版本 → 失败退出 7
- Postgres → 拒绝退出 3
- `--backup` 写 `.bak`
- 缺失 DB → 拒绝退出 4

CI 通过条件：`uv run pytest tests/unit/scripts/test_db_downgrade.py` 全绿。

## 8. 不在脚本范围

- 从 1.x 回到 0.x（**跨大版本**）：schema 已经不兼容，必须 `backup restore`。
- Postgres 实例：本脚本只操作 SQLite。
- 跨工作区文件迁移：agent workspace 目录结构变化应另外写
  `octop backup create --include-workspaces` + 旧 binary 还原，不要靠
  downgrade 脚本。
- `octop.infra.agents.experts.library.*` 内置专家库：内容变化属于发版变更，
  不属于 schema 变更。
