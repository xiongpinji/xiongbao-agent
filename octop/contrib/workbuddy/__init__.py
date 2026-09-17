# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: Copyright (c) 2026 xiongbao-agent contributors
# Third-party assets (WorkBuddy experts):
#   Copyright Tencent and respective authors.
#   Licensed under MIT (per vbarter/workbuddy-experts NOTICE).
#   NOTICES: see vendor/NOTICE
#
"""
wb2octop — WorkBuddy Expert to Octop Expert Converter
=====================================================

Converts WorkBuddy expert manifests (from vbarter/workbuddy-experts)
into Octop v1.0.0 expert library format.

Usage::

    from octop.contrib.workbuddy import WorkBuddyConverter
    from pathlib import Path

    cvt = WorkBuddyConverter(
        vendor_root=Path("vendor/"),
        octop_root=Path("src/octop/infra/agents/experts/library"),
    )
    report = cvt.batch_convert()
    print(report.summary())
"""

from __future__ import annotations

from .converter import WorkBuddyConverter
from .models import ConvertReport, ExpertConvertResult
from .team import (
    MemberCaller,
    MockMemberCaller,
    TeamAgentRuntime,
    TeamDefinition,
    parse_team_soul,
    write_team_artifacts,
)

# Bench is a subpackage — import explicitly via octop.contrib.workbuddy.bench

__all__ = [
    "WorkBuddyConverter",
    "ConvertReport",
    "ExpertConvertResult",
    "MemberCaller",
    "MockMemberCaller",
    "TeamAgentRuntime",
    "TeamDefinition",
    "parse_team_soul",
    "write_team_artifacts",
]
