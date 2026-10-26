"""CLEAR: Contextual, Lineage-aware, Escalating Agent-action Review.

A human-centred mediation layer that sits between an LLM agent and its tools.
It tracks the provenance of every value the agent may use, scores the
contextual risk of each proposed tool call, and escalates only the calls
that need human judgement -- presenting the evidence (where each argument
came from, which untrusted source looks like an injected instruction, and
how the action deviates from the user's stated intent) that a person needs
to make that judgement.
"""

from clear.manifest import ToolManifest, ToolSpec
from clear.provenance import ProvenanceLedger, Source, Attribution
from clear.signals import injection_likeness
from clear.envelope import IntentEnvelope, derive_envelope
from clear.risk import RiskModel, Assessment, Tier
from clear.mediator import Mediator, ToolCall
from clear.config import load_config

__all__ = [
    "ToolManifest", "ToolSpec", "ProvenanceLedger", "Source", "Attribution",
    "injection_likeness", "IntentEnvelope", "derive_envelope", "RiskModel",
    "Assessment", "Tier", "Mediator", "ToolCall", "load_config",
]

__version__ = "1.0.0"
