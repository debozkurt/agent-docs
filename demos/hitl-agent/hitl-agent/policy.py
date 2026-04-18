# policy.py
"""Which tools trigger which gate. One hardcoded map — swap for a function
when you need amount thresholds, compliance tiers, or time-of-day rules."""
from __future__ import annotations

from typing import Literal, Optional

GateKind = Literal["pre_approval", "post_review"]

GATE_POLICY: dict[str, GateKind] = {
    "send_message":           "pre_approval",
    "generate_campaign_list": "post_review",
}


def gate_for(tool_name: str) -> Optional[GateKind]:
    return GATE_POLICY.get(tool_name)
