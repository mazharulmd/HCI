"""The CLEAR mediator: the single interposition point between agent and tools.

Usage (framework-agnostic)::

    m = Mediator.default()
    m.start_task(user_prompt, system_prompt)
    for call in agent_proposed_calls:
        a = m.assess(call)                    # risk + tier + evidence
        decision = m.decide(a, human=ui)      # ALLOW/NOTIFY run; CONFIRM/FORCE ask
        if decision.execute:
            out = run_tool(call)
            m.observe_result(call, out)       # updates provenance ledger

The mediator never sees or trusts model reasoning; it only uses (i) the
user's prompt, (ii) tool outputs with their manifest trust labels and (iii)
the proposed call. It therefore cannot be prompt-injected itself.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from clear.config import load_config
from clear.envelope import IntentEnvelope, derive_envelope
from clear.manifest import ToolManifest
from clear.provenance import ProvenanceLedger
from clear.risk import Assessment, RiskModel, Tier


@dataclass
class ToolCall:
    function: str
    args: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass
class Decision:
    execute: bool
    tier: Tier
    asked_human: bool
    human_approved: bool | None = None
    note: str = ""


class HumanResponder(Protocol):
    def __call__(self, assessment: Assessment, mediator: "Mediator") -> bool: ...


class Mediator:
    def __init__(self, manifest: ToolManifest, cfg: dict, ablate: set[str] | None = None,
                 envelope_fn: Callable[[str], IntentEnvelope] = derive_envelope) -> None:
        self.manifest = manifest
        self.cfg = cfg
        self.risk = RiskModel(cfg, ablate)
        self.envelope_fn = envelope_fn
        self.ledger = ProvenanceLedger(cfg.get("provenance", {}).get("min_value_len", 3))
        self.envelope: IntentEnvelope = IntentEnvelope(prompt="")
        self.history: list[tuple[Assessment, Decision | None]] = []
        self.step = 0

    @classmethod
    def default(cls, ablate: set[str] | None = None, overrides: dict | None = None) -> "Mediator":
        return cls(ToolManifest.load(), load_config(overrides=overrides), ablate)

    # ------------------------------------------------------------ lifecycle
    def start_task(self, user_prompt: str, system_prompt: str | None = None,
                   envelope: IntentEnvelope | None = None) -> IntentEnvelope:
        self.ledger = ProvenanceLedger(self.cfg.get("provenance", {}).get("min_value_len", 3))
        if system_prompt:
            self.ledger.add_system(system_prompt)
        self.ledger.add_user(user_prompt)
        self.envelope = envelope or self.envelope_fn(user_prompt)
        self.history = []
        self.step = 0
        return self.envelope

    def observe_result(self, call: ToolCall, output: str | None) -> None:
        spec = self.manifest.get(call.function)
        self.ledger.add_tool_output(call.function, call.args, "" if output is None else str(output),
                                    trust=spec.output_trust, private=spec.private_output, step=self.step)

    # ------------------------------------------------------------ mediation
    def assess(self, call: ToolCall) -> Assessment:
        t0 = time.perf_counter()
        a = self.risk.assess(self.manifest.get(call.function), call.args, self.ledger, self.envelope)
        a.latency_ms = (time.perf_counter() - t0) * 1000.0
        self.step += 1
        return a

    def decide(self, a: Assessment, human: HumanResponder | None = None) -> Decision:
        if a.tier in (Tier.ALLOW, Tier.NOTIFY):
            d = Decision(True, a.tier, asked_human=False)
        elif human is None:
            d = Decision(False, a.tier, asked_human=False, note="no human available: fail closed")
        else:
            ok = bool(human(a, self))
            d = Decision(ok, a.tier, asked_human=True, human_approved=ok)
        self.history.append((a, d))
        return d
