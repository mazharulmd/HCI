"""Parametric model of a person answering agent-action confirmation dialogs.

THIS IS A SIMULATION MODEL, NOT HUMAN DATA. It is used (i) to make the
assumptions behind "human-in-the-loop" security explicit and (ii) to derive
hypotheses for the user study in docs/user_study/. Every parameter is varied
over a wide grid in the paper; no single setting is claimed to describe real
users.

Model
-----
Each dialog is a yes/no detection problem in equal-variance signal-detection
theory (SDT). The evidence a person extracts is x ~ N(+d/2, 1) for an
injected (malicious) action and x ~ N(-d/2, 1) for a benign one; the person
denies when x > c. Sensitivity d depends on what the dialog shows:

    d = d0                      generic dialog (tool name + arguments)
      + d_prov                  argument provenance + reasons are shown
      + d_force                 cognitive-forcing check (FORCE tier)

Habituation: with probability 1 - a(n) the person does not engage and
approves by default ("rubber-stamping"), where n is the number of dialogs of
the same interaction type already seen in the session and

    a(n) = a_min + (1 - a_min) * exp(-n / lam).

FORCE dialogs use a different interaction (the person must answer a question
about where a value came from before the approve button is enabled), so they
cannot be approved without engagement and keep their own exposure counter --
the mechanism by which differentiated warning interactions resist
generalisation of habituation in prior work.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import random


@dataclass(frozen=True)
class HumanParams:
    d0: float = 1.0
    d_prov: float = 1.0
    d_force: float = 0.5
    criterion: float = 0.0
    a_min: float = 0.3
    lam: float = 15.0
    force_engages: bool = True


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


@dataclass
class SimulatedUser:
    params: HumanParams
    rng: random.Random = field(default_factory=random.Random)
    seen: dict[str, int] = field(default_factory=lambda: {"confirm": 0, "force": 0})

    def attention(self, kind: str) -> float:
        p = self.params
        if kind == "force" and p.force_engages:
            return 1.0
        if math.isinf(p.lam):
            return 1.0
        return p.a_min + (1.0 - p.a_min) * math.exp(-self.seen[kind] / p.lam)

    def p_deny(self, injected: bool, kind: str, evidence: bool) -> float:
        """Probability of denying this dialog (before updating exposure)."""
        p = self.params
        d = p.d0 + (p.d_prov if evidence else 0.0) + (p.d_force if kind == "force" else 0.0)
        mu = d / 2.0 if injected else -d / 2.0
        engaged_deny = 1.0 - phi(p.criterion - mu)
        return self.attention(kind) * engaged_deny

    def respond(self, injected: bool, kind: str, evidence: bool) -> bool:
        """Return True if the user APPROVES the action."""
        deny = self.rng.random() < self.p_deny(injected, kind, evidence)
        self.seen[kind] += 1
        return not deny
