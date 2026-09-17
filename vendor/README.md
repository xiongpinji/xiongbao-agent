# Vendor assets

| Path | Role | In git? |
|---|---|---|
| `workbuddy-experts/` | Expert prompts (vbarter) — primary converter input | yes |
| `workbuddy-bench/` | Official Harbor evaluation framework (shallow clone) | yes |
| `RongXinAI/` | Expert lifecycle reference (zhiyuan-expert-manager lineage) | yes |
| `workbuddy-cdn-snapshot/` | Optional CDN mirror (may be empty) | yes if small |
| `workbuddyskills/` | Skills + connectors archive (~1.3GB) | **no — clone locally** |

```powershell
git clone --depth 1 https://github.com/infometa/workbuddyskills.git vendor/workbuddyskills
```

Converted experts already live under `octop/src/octop/infra/agents/experts/library/` — reconversion only needs `workbuddy-experts`.
