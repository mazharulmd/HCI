"""Contextual risk model and risk-adaptive escalation (patterns P3 + P4).

For a proposed call a = (f, args) the model computes interpretable features

    s      sensitivity of tool f                         (manifest)
    tau    provenance taint of target / value arguments  (ledger)
    kappa  private data flowing to a non-endorsed target (ledger)
    delta  deviation from the intent envelope            (envelope)
    iota   instruction-likeness of untrusted content the action depends on

and combines them into a heuristic score:

    Q(a) = 1 - prod_i (1 - w_i x_i)       (noisy-OR feature combination)
    R(a) = s(f) * Q(a)                     (severity-weighted risk index)

Q and R are not calibrated probabilities or expected losses. The weights are
design parameters, and the features are not independent random events.

R is mapped to four escalation tiers: ALLOW < NOTIFY < CONFIRM < FORCE.

Escalation floor (Proposition 1 in the paper): if s(f) >= s* and some target
argument is attributable only to untrusted content (tau = 1), then
R >= s* w_taint, independent of the attacker-controlled text. With the
default weights every side-effecting tool with s >= 0.4 therefore reaches at
least CONFIRM whenever its target is externally sourced -- an attacker cannot
talk the mediator out of escalating by rephrasing the injection.
"""
from __future__ import annotations

import enum
import math
import re
from dataclasses import dataclass, field
from typing import Any

from clear.envelope import IntentEnvelope
from clear.manifest import ToolSpec
from clear.provenance import Attribution, ProvenanceLedger, distinctive_tokens, flatten_values


class Tier(enum.IntEnum):
    ALLOW = 0     # execute silently (logged)
    NOTIFY = 1    # execute, show ambient non-blocking notice with undo
    CONFIRM = 2   # block until the user approves, showing provenance evidence
    FORCE = 3     # block; override requires a cognitive-forcing check


@dataclass
class Assessment:
    tool: str
    args: dict[str, Any]
    spec: ToolSpec
    features: dict[str, float]
    unintended_score: float
    risk: float
    tier: Tier
    arg_provenance: dict[str, list[Attribution]] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    evidence_sources: list[int] = field(default_factory=list)
    latency_ms: float = 0.0

    @property
    def escalated(self) -> bool:
        return self.tier >= Tier.CONFIRM

    def to_dict(self) -> dict:
        return {
            "tool": self.tool, "args": self.args, "capability": self.spec.capability,
            "sensitivity": self.spec.sensitivity, "reversible": self.spec.reversible,
            "features": self.features, "unintended_score": self.unintended_score, "risk": self.risk,
            "tier": self.tier.name, "reasons": self.reasons, "evidence_sources": self.evidence_sources,
            "arg_provenance": {k: [a.__dict__ for a in v] for k, v in self.arg_provenance.items()},
            "latency_ms": self.latency_ms,
        }


def _short(v: Any, n: int = 48) -> str:
    s = str(v)
    return s if len(s) <= n else s[: n - 3] + "..."


_STOP = {"the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "at", "by", "with", "from", "my", "me", "i",
         "is", "are", "be", "it", "this", "that", "please", "can", "you", "your", "do", "all", "as", "into", "about"}
_TOK = re.compile(r"[a-z0-9]+")


def _bag(text: str) -> set[str]:
    out = set()
    for t in _TOK.findall(text.lower()):
        if t in _STOP or len(t) < 2:
            continue
        out.add(t[:-1] if t.endswith("s") and len(t) > 3 else t)
    return out


def goal_drift(prompt: str, spec: ToolSpec, args: dict) -> float:
    """Lexical goal-mismatch between the user's request and the proposed action (0 = aligned, 1 = disjoint).

    Inspired by the semantic-drift pattern (CGASD) of the PROV-Guard iteration. Only
    the goal-mismatch component is kept: its capability-escalation and entity-diversion
    components duplicate CLEAR's deviation and taint features.
    """
    from clear.envelope import CAPABILITY_LEXICON
    action = " ".join([spec.name.replace("_", " ")] + [w.replace("\\", "") for w in CAPABILITY_LEXICON.get(spec.capability, [])]
                      + [str(v) for n in (*spec.target_args, *spec.value_args) for v in flatten_values(args.get(n))])
    a, u = _bag(action), _bag(prompt)
    if not a or not u:
        return 1.0
    return 1.0 - len(a & u) / math.sqrt(len(a) * len(u))


class RiskModel:
    def __init__(self, cfg: dict, ablate: set[str] | None = None) -> None:
        self.r = cfg["risk"]
        self.t = cfg["tiers"]
        self.p = cfg.get("provenance", {})
        # ablation switches: {"taint", "exfil", "deviation", "injection", "tiers"}
        self.ablate = set(ablate or ())

    # ------------------------------------------------------------------ features
    def _taint(self, spec: ToolSpec, args: dict, ledger: ProvenanceLedger,
               prov: dict[str, list[Attribution]], reasons: list[str], evidence: set[int]) -> float:
        tau = 0.0
        for name in spec.target_args:
            for att in prov.get(name, []):
                if att.origin == "external":
                    tau = max(tau, self.r["taint_external"])
                    srcs = ", ".join(ledger.sources[i].label for i in att.sources[:2])
                    reasons.append(f"Target '{_short(att.value)}' ({name}) appears only in untrusted content: {srcs}")
                    evidence.update(att.sources)
                elif att.origin == "unattributed":
                    tau = max(tau, self.r["taint_unattributed"])
                    reasons.append(f"Target '{_short(att.value)}' ({name}) does not appear in your request or any trusted source")
        for name in spec.value_args:
            for att in prov.get(name, []):
                if att.origin == "external":
                    tau = max(tau, self.r["taint_value_external"])
                    reasons.append(f"Value '{_short(att.value)}' ({name}) was copied from untrusted content")
                    evidence.update(att.sources)
        # links / addresses / account numbers planted into outgoing content
        for name in spec.content_args:
            for tok in sorted(distinctive_tokens(" ".join(flatten_values(args.get(name))))):
                att = ledger.attribute(tok)
                if att.origin == "external":
                    tau = max(tau, self.r.get("taint_content_external", 0.0))
                    reasons.append(f"The {name} contains '{_short(tok)}', which comes from untrusted content "
                                   f"({ledger.sources[att.sources[0]].label})")
                    evidence.update(att.sources)
                    break
        return tau

    def _exfil(self, spec: ToolSpec, args: dict, ledger: ProvenanceLedger,
               prov: dict[str, list[Attribution]], reasons: list[str], evidence: set[int]) -> float:
        if spec.capability not in ("communicate", "web_fetch", "calendar_write", "workspace_admin"):
            return 0.0
        targets = [a for n in spec.target_args for a in prov.get(n, [])]
        endorsed = targets and all(a.origin in ("user", "trivial") for a in targets)
        if endorsed:
            return 0.0
        payload = " ".join(str(args.get(n, "") or "") for n in (*spec.content_args, *spec.target_args))
        carried = ledger.private_data_carried(
            payload, self.p.get("shingle_words", 5), self.p.get("content_overlap_threshold", 0.3))
        if carried:
            reasons.append("Sends your private data (from "
                           + ", ".join(ledger.sources[i].label for i in carried[:2])
                           + ") to a recipient you did not name")
            evidence.update(carried)
            return 1.0
        return 0.0

    def _deviation(self, spec: ToolSpec, envelope: IntentEnvelope, reasons: list[str]) -> float:
        if not spec.is_side_effecting or envelope.allows(spec.capability):
            return 0.0
        if envelope.delegated:
            reasons.append(f"Action type '{spec.capability}' was not requested directly, "
                           "but you asked the agent to follow instructions found in your data")
            return self.r["deviation_delegated"]
        reasons.append(f"Action type '{spec.capability}' is outside what your request asked for")
        return 1.0

    def _injection(self, ledger: ProvenanceLedger, prov: dict[str, list[Attribution]],
                   reasons: list[str], evidence: set[int]) -> tuple[float, float]:
        attributed = {i for atts in prov.values() for a in atts if a.origin == "external" for i in a.sources}
        iota_attr = max((ledger.sources[i].injection_score for i in attributed), default=0.0)
        top = max(ledger.untrusted_sources(), key=lambda s: s.injection_score, default=None)
        iota_ctx = (top.injection_score if top else 0.0) * self.r["injection_context_weight"]
        if top is not None and max(iota_attr, top.injection_score) >= 0.5:
            span = next(iter(top.injection_spans), None)
            quote = f": \"{_short(span.text, 70)}\"" if span else ""
            reasons.append(f"Content read from {top.label} contains text addressed to the AI agent{quote}")
            evidence.add(top.sid)
        elif top is not None and top.injection_score > 0:
            reasons.append(f"Content read from {top.label} contains some instruction-like phrasing (weak signal)")
            evidence.add(top.sid)
        return iota_attr, iota_ctx

    # ------------------------------------------------------------------ main
    def assess(self, spec: ToolSpec, args: dict, ledger: ProvenanceLedger,
               envelope: IntentEnvelope) -> Assessment:
        args = dict(args or {})
        reasons: list[str] = []
        evidence: set[int] = set()
        prov = {k: ledger.attribute_arg(v) for k, v in args.items()}
        if not spec.is_side_effecting and spec.sensitivity == 0.0:
            return Assessment(spec.name, args, spec, {"s": 0.0}, 0.0, 0.0, Tier.ALLOW, prov)

        tau = 0.0 if "taint" in self.ablate else self._taint(spec, args, ledger, prov, reasons, evidence)
        kappa = 0.0 if "exfil" in self.ablate else self._exfil(spec, args, ledger, prov, reasons, evidence)
        delta = 0.0 if "deviation" in self.ablate else self._deviation(spec, envelope, reasons)
        if "injection" in self.ablate:
            iota_attr = iota_ctx = 0.0
        else:
            iota_attr, iota_ctx = self._injection(ledger, prov, reasons, evidence)
        iota = max(iota_attr, iota_ctx)

        x = {"tau": tau, "kappa": kappa, "delta": delta, "iota": iota}
        w = {"tau": self.r["w_taint"], "kappa": self.r["w_exfil"],
             "delta": self.r["w_deviation"], "iota": self.r["w_injection"]}
        if self.r.get("w_drift", 0.0) > 0 and "drift" not in self.ablate:
            x["gamma"] = goal_drift(ledger.user_text, spec, args)
            w["gamma"] = self.r["w_drift"]
            if x["gamma"] >= 0.9:
                reasons.append("The action has little in common with what you asked for")
        remaining = 1.0
        for k in x:
            remaining *= 1.0 - w[k] * x[k]
        q = 1.0 - remaining
        risk = spec.sensitivity * q
        tier = self.tier_of(risk, spec)
        if tier == Tier.CONFIRM and risk < self.t["confirm"]:
            reasons.append("This action cannot be undone, so it needs your confirmation")
        feats = {"s": spec.sensitivity, **x, "iota_attr": iota_attr, "iota_ctx": iota_ctx}
        return Assessment(spec.name, args, spec, feats, q, risk, tier, prov, reasons, sorted(evidence))

    def tier_of(self, risk: float, spec: ToolSpec) -> Tier:
        if "tiers" in self.ablate:
            # single-threshold variant: anything above NOTIFY is a confirmation
            return Tier.CONFIRM if risk >= self.t["notify"] else Tier.ALLOW
        if risk >= self.t["force"]:
            return Tier.FORCE
        if risk >= self.t["confirm"]:
            return Tier.CONFIRM
        if risk >= self.t["notify"]:
            if self.t.get("promote_irreversible_notify", True) and not spec.reversible:
                return Tier.CONFIRM
            return Tier.NOTIFY
        return Tier.ALLOW
