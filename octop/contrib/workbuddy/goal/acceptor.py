# SPDX-License-Identifier: MIT
"""Acceptance checker — verify Goal criteria against work_dir artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AcceptanceCriterion, CriterionResult


def _safe_under(work_dir: Path, rel: str) -> Path | None:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    path = (work_dir / "files" / rel).resolve()
    root = (work_dir / "files").resolve()
    if not str(path).startswith(str(root)):
        return None
    return path


def check_criterion(
    criterion: AcceptanceCriterion,
    *,
    work_dir: Path,
    step_results: list[dict[str, Any]],
) -> CriterionResult:
    kind = criterion.check
    if kind == "always":
        return CriterionResult(criterion.id, True, "always")

    if kind == "file_exists":
        path = _safe_under(work_dir, criterion.path)
        if path is None:
            return CriterionResult(criterion.id, False, "invalid path")
        ok = path.is_file()
        return CriterionResult(criterion.id, ok, str(path) if ok else f"missing: {criterion.path}")

    if kind == "file_contains":
        path = _safe_under(work_dir, criterion.path)
        if path is None or not path.is_file():
            return CriterionResult(criterion.id, False, f"missing: {criterion.path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        needle = criterion.substring or ""
        ok = needle in text if needle else bool(text.strip())
        return CriterionResult(
            criterion.id,
            ok,
            f"found substring ({len(needle)} chars)" if ok else "substring not found",
        )

    if kind == "outbox_message":
        outbox = work_dir / "outbox" / "messages.jsonl"
        if not outbox.is_file():
            return CriterionResult(criterion.id, False, "outbox missing")
        want = (criterion.target or "").strip().lower()
        for line in outbox.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            tgt = str(row.get("target") or "").lower()
            if not want or want == tgt or want in tgt:
                return CriterionResult(criterion.id, True, f"matched target={row.get('target')}")
        return CriterionResult(criterion.id, False, f"no message for {criterion.target or '*'}")

    if kind == "step_ok":
        si = criterion.step_index
        if si is None:
            return CriterionResult(criterion.id, False, "step_index missing")
        for row in step_results:
            if int(row.get("index", -1)) == int(si):
                ok = bool(row.get("ok"))
                return CriterionResult(
                    criterion.id,
                    ok,
                    "step ok" if ok else str(row.get("error") or "step failed"),
                )
        return CriterionResult(criterion.id, False, f"step {si} not run")

    return CriterionResult(criterion.id, False, f"unknown check: {kind}")


def accept_all(
    criteria: list[AcceptanceCriterion],
    *,
    work_dir: Path,
    step_results: list[dict[str, Any]],
) -> tuple[bool, list[CriterionResult]]:
    results: list[CriterionResult] = []
    all_ok = True
    for c in criteria:
        r = check_criterion(c, work_dir=work_dir, step_results=step_results)
        results.append(r)
        if c.required and not r.ok:
            all_ok = False
    return all_ok, results
