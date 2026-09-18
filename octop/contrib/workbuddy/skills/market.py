# SPDX-License-Identifier: MIT
"""Skill market install + heuristic security scanner."""

from __future__ import annotations

import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Heuristic patterns that warrant review (not automatic block in install).
_RISKY_PATTERNS: list[tuple[str, str]] = [
    (r"\bos\.system\s*\(", "os.system call"),
    (r"\bsubprocess\.(call|run|Popen)\s*\(", "subprocess invocation"),
    (r"\beval\s*\(", "eval()"),
    (r"\bexec\s*\(", "exec()"),
    (r"curl\s+[^\n]*\|\s*(ba)?sh", "curl pipe to shell"),
    (r"rm\s+-rf\s+/", "destructive rm -rf /"),
    (r"base64\s+-d", "base64 decode pipeline"),
    (r"powershell\s+-enc", "encoded PowerShell"),
    (r"__import__\s*\(\s*['\"]os['\"]", "dynamic os import"),
]


@dataclass
class ScanFinding:
    severity: str  # info | warn | high
    path: str
    rule: str
    line: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanReport:
    skill_id: str
    path: str
    findings: list[ScanFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == "high" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "path": self.path,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


def scan_skill_dir(skill_dir: Path | str) -> ScanReport:
    root = Path(skill_dir)
    skill_id = root.name
    findings: list[ScanFinding] = []
    if not root.is_dir():
        return ScanReport(skill_id=skill_id, path=str(root), findings=[
            ScanFinding("high", str(root), "missing_dir", 0, "skill directory missing")
        ])
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".py", ".sh", ".js", ".ts", ".ps1", ".bat", ".cmd"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for i, line in enumerate(text.splitlines(), start=1):
            for pattern, label in _RISKY_PATTERNS:
                if re.search(pattern, line, flags=re.IGNORECASE):
                    sev = "high" if "rm -rf" in label or "pipe to shell" in label else "warn"
                    findings.append(
                        ScanFinding(sev, rel, label, i, line.strip()[:160])
                    )
    if not (root / "SKILL.md").is_file():
        findings.append(ScanFinding("warn", "SKILL.md", "missing_skill_md", 0, "SKILL.md not found"))
    return ScanReport(skill_id=skill_id, path=str(root), findings=findings)


def install_skill(
    source: Path | str,
    dest_root: Path | str,
    *,
    force: bool = False,
    require_scan_ok: bool = False,
) -> dict[str, Any]:
    """Copy a skill directory into dest_root/<name>/."""
    src = Path(source)
    if src.is_file() and src.name == "SKILL.md":
        src = src.parent
    if not src.is_dir():
        raise FileNotFoundError(f"skill source not found: {source}")
    dest_root = Path(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / src.name
    report = scan_skill_dir(src)
    if require_scan_ok and not report.ok:
        return {"installed": False, "dest": str(dest), "scan": report.to_dict()}
    if dest.exists():
        if not force:
            raise FileExistsError(f"already installed: {dest}")
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return {"installed": True, "dest": str(dest), "scan": report.to_dict()}


def install_from_vendor(
    skill_id: str,
    dest_root: Path | str,
    *,
    vendor_skills: Path | str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    vendor = Path(vendor_skills) if vendor_skills else (
        Path(__file__).resolve().parents[4] / "vendor" / "workbuddyskills" / "skills"
    )
    src = vendor / skill_id
    if not src.is_dir():
        # try builtin
        builtin = Path(__file__).resolve().parents[4] / "vendor" / "workbuddy-experts" / "builtin-skills" / skill_id
        src = builtin if builtin.is_dir() else src
    return install_skill(src, dest_root, force=force)
