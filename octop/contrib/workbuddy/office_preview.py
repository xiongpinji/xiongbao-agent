# SPDX-License-Identifier: MIT
"""Lightweight Office text extract for preview (docx / xlsx via zip+xml)."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_W_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_A_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_MAX = 80_000


def _strip_text(xml: str) -> str:
    # fallback if namespaces odd
    return re.sub(r"<[^>]+>", " ", xml)


def extract_docx_text(path: Path | str) -> str:
    p = Path(path)
    parts: list[str] = []
    with zipfile.ZipFile(p) as zf:
        name = "word/document.xml"
        if name not in zf.namelist():
            return ""
        root = ET.fromstring(zf.read(name))
        for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
            if node.text:
                parts.append(node.text)
            if node.tail:
                parts.append(node.tail)
        if not parts:
            parts.append(_strip_text(zf.read(name).decode("utf-8", errors="replace")))
    text = "\n".join(x for x in parts if x.strip())
    return text[:_MAX]


def extract_xlsx_text(path: Path | str) -> str:
    p = Path(path)
    lines: list[str] = []
    with zipfile.ZipFile(p) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                texts = [
                    t.text or ""
                    for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                ]
                shared.append("".join(texts))
        sheets = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        for sheet in sheets[:5]:
            lines.append(f"## {Path(sheet).name}")
            root = ET.fromstring(zf.read(sheet))
            for c in root.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                ref = c.attrib.get("r", "")
                v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                if v is None or v.text is None:
                    continue
                val = v.text
                if c.attrib.get("t") == "s":
                    try:
                        val = shared[int(val)]
                    except (ValueError, IndexError):
                        pass
                lines.append(f"{ref}\t{val}")
            if len("\n".join(lines)) > _MAX:
                break
    return "\n".join(lines)[:_MAX]


def office_preview(path: Path | str) -> dict[str, str | bool]:
    p = Path(path)
    ext = p.suffix.lower()
    try:
        if ext == ".docx":
            content = extract_docx_text(p)
            return {"ok": True, "format": "text", "content_type": "text/plain", "content": content or "(empty docx)"}
        if ext == ".xlsx":
            content = extract_xlsx_text(p)
            return {"ok": True, "format": "text", "content_type": "text/plain", "content": content or "(empty xlsx)"}
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        return {"ok": False, "format": "text", "content_type": "text/plain", "content": "", "error": str(exc)}
    return {"ok": False, "format": "text", "error": f"unsupported office type: {ext}"}
