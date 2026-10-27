"""
PROV-Guard: Human-Computer Interaction Defense Framework Against Indirect Prompt Injection
in Tool-Augmented AI Agents.

Core Modules:
- models: Data structures for tool calls, context chunks, provenance tags, and UI interventions
- provenance: Dual-Lineage Provenance Attribution (DLPA) taint tracking engine
- drift: Contextual Goal-Alignment & Semantic Drift Visualization (CGASD) scorer
- risk_gate: Adaptive Friction & Tiered Capability Gates (AFTCG) & Counterfactual Preview (ICSP)
- user_model: Cognitive & Behavioral Human-in-the-Loop Simulator (Habituation, SDT, NASA-TLX)
"""

from .models import (
    TrustLevel,
    CapabilityTier,
    FrictionLevel,
    AttackCategory,
    ContextChunk,
    ToolParameter,
    ToolCallProposal,
    ProvenanceSpan,
    RiskAssessment,
    InterventionUI,
    UserDecisionOutcome,
)
from .provenance import ProvenanceTracker
from .drift import SemanticDriftScorer
from .risk_gate import PROVGuardEngine, DefenseConfig

__version__ = "1.0.0"
__all__ = [
    "TrustLevel",
    "CapabilityTier",
    "FrictionLevel",
    "AttackCategory",
    "ContextChunk",
    "ToolParameter",
    "ToolCallProposal",
    "ProvenanceSpan",
    "RiskAssessment",
    "InterventionUI",
    "UserDecisionOutcome",
    "ProvenanceTracker",
    "SemanticDriftScorer",
    "PROVGuardEngine",
    "DefenseConfig",
]
