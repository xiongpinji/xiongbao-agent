# 企业包装（文档门禁）

本目录描述 **可选** 企业组件；默认开源/本地部署 **不启用**。
不把真实密钥、租户 ID、连接串提交进仓库。

## systemd（已提供单元文件）

路径：`deploy/systemd/`

| 单元 | 作用 |
|---|---|
| `octop.service` | 常驻 API（`octop run`） |
| `octop-tick.service` | 一次性 Routine `tick` |
| `octop-tick.timer` | 每分钟触发 tick |

安装示例（Linux）：

```bash
sudo cp deploy/systemd/octop.service /etc/systemd/system/
sudo cp deploy/systemd/octop-tick.service /etc/systemd/system/
sudo cp deploy/systemd/octop-tick.timer /etc/systemd/system/
# 编辑路径 / User / EnvironmentFile 后：
sudo systemctl daemon-reload
sudo systemctl enable --now octop.service
sudo systemctl enable --now octop-tick.timer
```

Windows 等价物见 `scripts/windows/register_routine_tick.ps1`（V5.1）。

建议环境文件（**勿入库**）`/etc/octop/octop.env`：

```bash
OCTOP_HOME=/var/lib/octop
WB_LLM_BASE_URL=http://127.0.0.1:11434/v1
WB_LLM_MODEL=qwen2.5:3b
# WB_ALLOW_OUTBOUND=0
```

## Casdoor（可选 SSO）

**门禁**：仅当运维明确启用企业 SSO 时配置；本仓库不内嵌 Casdoor 二进制。

建议：

1. 独立部署 Casdoor（官方 compose / Helm）。
2. 在 Octop 侧通过反向代理或网关校验 JWT（实现点：Octop `api` JWT 中间件扩展）。
3. 环境变量约定（示例，未接线前仅作文档）：

| 变量 | 含义 |
|---|---|
| `OCTOP_CASDOOR_ENDPOINT` | Casdoor 公网/内网 URL |
| `OCTOP_CASDOOR_CLIENT_ID` | OAuth client id |
| `OCTOP_CASDOOR_CLIENT_SECRET` | 存 secret 管理器，不进 git |
| `OCTOP_CASDOOR_ORG` | 组织名 |
| `OCTOP_CASDOOR_APP` | 应用名 |

未设置上述变量时，行为保持本地用户/密码或现有 JWT，**不连接 Casdoor**。

## Milvus（可选向量库）

**门禁**：仅知识检索 / RAG 企业场景启用；默认文件记忆（`MEMORY.md`）足够。

| 变量 | 含义 |
|---|---|
| `OCTOP_MILVUS_URI` | 例如 `http://127.0.0.1:19530` |
| `OCTOP_MILVUS_TOKEN` | 可选鉴权 |
| `OCTOP_MILVUS_COLLECTION` | 集合名 |

未设置 `OCTOP_MILVUS_URI` 时，不加载 Milvus 客户端，不阻塞启动。

## 验收

```bash
python -S scripts/verify_v5.py
# 检查 deploy/systemd/* 与 deploy/enterprise/README.md 存在
```
