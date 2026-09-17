# V1 Deliverable Checklist

**Status: READY** (verified locally)

## Acceptance

```powershell
python -S scripts\verify_v1.py
# → V1 VERIFY OK — deliverable ready
```

| Check | Result |
|---|---|
| Converter unit tests | 8/8 |
| Team runtime tests | 11/11 |
| Bench unit tests | 4/4 |
| Smoke-50 bench | 50/50 (100%) |
| StockPartnerTeam demo | OK |

## Artifacts

After verify, see `artifacts/bench/`:

- `smoke_sample.json` — 50 task definitions
- `metrics.jsonl` — per-task observability events
- `report.json` — aggregate scores
- `office_listed.json` — official Office tasks if HF dataset present (0 when offline)

## Out of scope (V2 / enterprise)

- Teach recorder + Routine engine
- Casdoor / Milvus / systemd packaging
- Live LLM scoring on Harbor office/code/web/sec subsets
