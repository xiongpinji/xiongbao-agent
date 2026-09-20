"""
Octop performance baseline.

Measures two cold-start timings against an isolated Octop workspace so the
real user data is never touched:

  1. **OctopServer.start()** — wall clock from server construction to
     `services.db` being open, migrations applied, and runtime booted.
  2. **HTTP round-trip** via Starlette `TestClient` against the FastAPI
     `build_app(server)` for `/api/health`.

The benchmark is CI-friendly: it runs against the project's `.venv`, writes
nothing under the user's `~/.octop/`, and exits 1 when either median drifts
past its budget.

Run from `octop/`:

    uv run python scripts/perf_baseline.py

Budgets (seconds, median over 5 samples):
  - server.start() ≤ 8.0
  - /api/health round-trip ≤ 0.25
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

STARTUP_BUDGET_S = 8.0
HTTP_LATENCY_BUDGET_S = 0.25
SAMPLE_COUNT = 5


def _isolated_home() -> Path:
    base = Path(tempfile.mkdtemp(prefix="octop-perf-"))
    (base / "agents").mkdir(parents=True, exist_ok=True)
    return base


async def _measure_startup(home: Path, samples: int) -> list[float]:
    from octop.infra.server import OctopServer

    timings: list[float] = []
    for _ in range(samples):
        server = OctopServer(home)
        started = time.monotonic()
        await server.start()
        timings.append(time.monotonic() - started)
        await server.stop()
    return timings


def _measure_http_latency(server, samples: int) -> list[float]:
    from fastapi.testclient import TestClient

    from octop.api.app import build_app

    app = build_app(server)
    timings: list[float] = []
    with TestClient(app) as client:
        for _ in range(samples):
            started = time.monotonic()
            response = client.get("/api/health")
            assert response.status_code == 200, response.text
            timings.append(time.monotonic() - started)
    return timings


def _report(name: str, samples: list[float], budget_s: float) -> bool:
    if not samples:
        print(f"[perf] {name}: no samples")
        return True
    median = statistics.median(samples)
    p95 = sorted(samples)[max(0, int(len(samples) * 0.95) - 1)]
    ok = median <= budget_s
    status = "PASS" if ok else "FAIL"
    print(
        f"[perf] {name}: median={median * 1000:.0f}ms p95={p95 * 1000:.0f}ms "
        f"budget={budget_s * 1000:.0f}ms -> {status}"
    )
    return ok


async def main() -> int:
    home = _isolated_home()
    os.environ["OCTOP_HOME"] = str(home)
    print(f"[perf] isolated home: {home}")

    # Warm-up: pre-import to avoid counting module-import jitter on the first
    # measurement. Subsequent samples include import cost only if Python reuses
    # the cached bytecode, which is the realistic baseline.
    from octop.infra.server import OctopServer  # noqa: F401

    startup_timings = await _measure_startup(home, SAMPLE_COUNT)

    # HTTP latency needs a live server — start one more and tear it down.
    http_server = OctopServer(home)
    try:
        await http_server.start()
        http_timings = _measure_http_latency(http_server, SAMPLE_COUNT)
    finally:
        await http_server.stop()

    results = [
        ("server-startup", startup_timings, STARTUP_BUDGET_S),
        ("http-latency", http_timings, HTTP_LATENCY_BUDGET_S),
    ]
    failed = [name for name, samples, budget in results if not _report(name, samples, budget)]
    if failed:
        print(f"[perf] REGRESSION: {', '.join(failed)}")
        return 1
    print("[perf] all baselines within budget")
    return 0


if __name__ == "__main__":
    import asyncio

    sys.exit(asyncio.run(main()))
