"""Data models for the wb2octop converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ExpertConvertResult:
    """Result of converting a single WorkBuddy expert."""

    expert_id: str
    kind: str  # "agent" | "team" | "plugin"
    success: bool
    src_path: Path | None = None
    dst_path: Path | None = None
    error: str | None = None
    skipped: bool = False  # True when source file is missing

    def __repr__(self) -> str:
        status = "OK" if (self.success and not self.skipped) else ("SKIP" if self.skipped else "FAIL")
        return f"<ConvertResult {self.expert_id}[{self.kind}] {status}>"


@dataclass
class ConvertReport:
    """Aggregate report for a full batch conversion run."""

    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None

    total: int = 0
    succeeded: int = 0
    skipped: int = 0
    failed: int = 0

    agents_converted: int = 0
    teams_converted: int = 0
    plugins_converted: int = 0

    results: list[ExpertConvertResult] = field(default_factory=list)

    def add(self, r: ExpertConvertResult) -> None:
        self.results.append(r)
        self.total += 1
        if r.success and not r.skipped:
            self.succeeded += 1
            if r.kind == "agent":
                self.agents_converted += 1
            elif r.kind == "team":
                self.teams_converted += 1
            elif r.kind == "plugin":
                self.plugins_converted += 1
        elif r.skipped:
            self.skipped += 1
        else:
            self.failed += 1

    def finish(self) -> None:
        self.finished_at = datetime.utcnow()

    def summary(self) -> str:
        elapsed = ""
        if self.finished_at:
            delta = self.finished_at - self.started_at
            elapsed = f" ({delta.total_seconds():.1f}s)"
        return (
            f"ConvertReport{elapsed}: {self.total} total | "
            f"{self.succeeded} OK | {self.skipped} skip | {self.failed} fail\n"
            f"  agents={self.agents_converted} teams={self.teams_converted} plugins={self.plugins_converted}"
        )

    def failed_results(self) -> list[ExpertConvertResult]:
        return [r for r in self.results if not r.success and not r.skipped]
