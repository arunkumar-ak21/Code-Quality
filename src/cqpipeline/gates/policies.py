"""
Gates policies module — named policy definitions for reuse.

Each policy encapsulates a specific set of rules for gate evaluation.
Organizations can define custom policies and apply them per-project.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cqpipeline.core.constants import GateAction, Severity


@dataclass
class Policy:
    """A named policy with severity-to-action mappings and thresholds."""

    name: str
    description: str = ""
    severity_actions: dict[str, str] = field(default_factory=lambda: {
        "critical": "block",
        "high": "block",
        "medium": "warn",
        "low": "info",
        "info": "ignore",
    })
    max_findings: dict[str, int] = field(default_factory=lambda: {
        "critical": 0,
        "high": 0,
        "total": 50,
    })


# ─── Pre-defined Policies ────────────────────────────────────────────

STRICT_POLICY = Policy(
    name="strict",
    description="Zero tolerance — blocks on any medium+ finding",
    severity_actions={
        "critical": "block",
        "high": "block",
        "medium": "block",
        "low": "warn",
        "info": "ignore",
    },
    max_findings={"critical": 0, "high": 0, "medium": 0, "total": 10},
)

STANDARD_POLICY = Policy(
    name="standard",
    description="Standard policy — blocks on high+, warns on medium",
    severity_actions={
        "critical": "block",
        "high": "block",
        "medium": "warn",
        "low": "info",
        "info": "ignore",
    },
    max_findings={"critical": 0, "high": 0, "total": 50},
)

LENIENT_POLICY = Policy(
    name="lenient",
    description="Lenient policy — only blocks on critical, good for onboarding",
    severity_actions={
        "critical": "block",
        "high": "warn",
        "medium": "info",
        "low": "ignore",
        "info": "ignore",
    },
    max_findings={"critical": 0, "high": 10, "total": -1},
)

# Registry of available policies
POLICY_REGISTRY: dict[str, Policy] = {
    "strict": STRICT_POLICY,
    "standard": STANDARD_POLICY,
    "lenient": LENIENT_POLICY,
}


def get_policy(name: str) -> Policy:
    """Get a named policy from the registry."""
    if name not in POLICY_REGISTRY:
        available = ", ".join(POLICY_REGISTRY.keys())
        raise ValueError(
            f"Unknown policy '{name}'. Available: {available}"
        )
    return POLICY_REGISTRY[name]
