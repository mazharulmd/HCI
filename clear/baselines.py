"""Tool-call-level baseline mediators, implemented on the same substrate as CLEAR.

* ConfirmAll   -- the de-facto industry pattern: every side-effecting call
                  requires user confirmation (no evidence beyond the call).
* StrictIFC    -- information-flow policy in the spirit of CaMeL / FIDES:
                  automatically deny a side-effecting call whose target or
                  value arguments are not endorsed by the user or a trusted
                  source, or that carries private data to a non-endorsed
                  target. No human in the loop.
* EnvelopeOnly -- task-scoped least privilege in the spirit of Progent /
                  ClawGuard: automatically deny side-effecting calls whose
                  capability is outside the intent envelope.
* InjectionDetector -- input-side detection: abort the episode as soon as an
                  untrusted tool output looks like an injected instruction
                  (mirrors AgentDojo's `transformers_pi_detector`, which
                  aborts the agent; here with CLEAR's lexical scorer).

Each baseline exposes ``decide(spec, assessment) -> str`` returning
"allow" | "confirm" | "deny" so that the replay harness treats all
mediators uniformly.
"""
from __future__ import annotations

from clear.manifest import ToolSpec
from clear.risk import Assessment


class ConfirmAll:
    name = "confirm_all"

    def decide(self, spec: ToolSpec, a: Assessment) -> str:
        return "confirm" if spec.is_side_effecting else "allow"


class StrictIFC:
    name = "strict_ifc"

    def decide(self, spec: ToolSpec, a: Assessment) -> str:
        if not spec.is_side_effecting:
            return "allow"
        f = a.features
        return "deny" if (f.get("tau", 0) > 0 or f.get("kappa", 0) > 0) else "allow"


class EnvelopeOnly:
    name = "envelope_only"

    def decide(self, spec: ToolSpec, a: Assessment) -> str:
        if not spec.is_side_effecting:
            return "allow"
        return "deny" if a.features.get("delta", 0) >= 1.0 else "allow"


class InjectionDetector:
    name = "pi_detector"

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def flags(self, injection_score: float) -> bool:
        return injection_score >= self.threshold
