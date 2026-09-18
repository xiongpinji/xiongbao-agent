# SPDX-License-Identifier: MIT
"""Goal / Craft package — plan → execute → accept (V3 MVP)."""

from __future__ import annotations

from .acceptor import accept_all, check_criterion
from .engine import GoalEngine
from .models import (
    AcceptanceCriterion,
    CriterionResult,
    GoalPlan,
    GoalRun,
    PlanStep,
)
from .planner import plan_goal
from .store import GoalStore

__all__ = [
    "AcceptanceCriterion",
    "CriterionResult",
    "GoalEngine",
    "GoalPlan",
    "GoalRun",
    "GoalStore",
    "PlanStep",
    "accept_all",
    "check_criterion",
    "plan_goal",
]
