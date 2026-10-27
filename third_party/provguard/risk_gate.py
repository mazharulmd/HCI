"""
Pattern 3 (AFTCG) & Pattern 4 (ICSP): Adaptive Friction & Tiered Capability Gates
and Interactive Counterfactual & Sandbox Preview Engine.

Also implements baseline defense architectures for rigorous empirical comparison:
- B0: No Defense (Autonomous execution)
- B1: Delimiter / Spotlighting System-Only Guard (Hines et al., 2024)
- B2: Static Telemetry Warning Banner (Persistent inline warning)
- B3: Uniform Binary Confirmation Modal (Magentic-UI Action Guard / MCP default dialog)
- PROV-Guard (Full & Ablations): Causal-Provenance & Contextual Risk UI
"""

import time
from dataclasses import dataclass
from typing import Tuple, List
from .models import (
    ToolCallProposal,
    RiskAssessment,
    InterventionUI,
    FrictionLevel,
    CapabilityTier,
    TrustLevel,
    CAPABILITY_WEIGHTS,
)
from .provenance import ProvenanceTracker
from .drift import SemanticDriftScorer


@dataclass
class DefenseConfig:
    """Configuration for baseline and PROV-Guard ablation conditions."""
    mode: str = "PROV_GUARD_FULL"
    # Feature toggles for PROV-Guard ablation studies
    enable_dlpa: bool = True    # Pattern 1: Dual-Lineage Provenance Attribution
    enable_cgasd: bool = True   # Pattern 2: Contextual Goal-Alignment & Semantic Drift
    enable_aftcg: bool = True   # Pattern 3: Adaptive Friction & Tiered Capability Gates
    enable_icsp: bool = True    # Pattern 4: Interactive Counterfactual & Sandbox Preview
    # Risk weights (alpha, beta, gamma)
    alpha_taint: float = 0.45
    beta_drift: float = 0.35
    gamma_capability: float = 0.20
    # Tier thresholds
    theta_tier1: float = 0.28
    theta_tier2: float = 0.50
    theta_tier3: float = 0.72


class PROVGuardEngine:
    """
    Core runtime controller that evaluates a proposed AI agent tool call, computes
    provenance lineage, semantic drift, capability blast radius, and synthesizes the
    corresponding HCI intervention artifact.
    """

    def __init__(self, config: DefenseConfig = None):
        self.config = config or DefenseConfig()
        self.provenance_tracker = ProvenanceTracker()
        self.drift_scorer = SemanticDriftScorer()

    @staticmethod
    def _compute_blast_radius(proposal: ToolCallProposal, untrusted_sinks: List[str]) -> Tuple[str, float]:
        """
        Pattern 4 (ICSP): Simulate counterfactual state diff and reversibility score.
        Returns (blast_radius_summary, reversibility_score in [0, 1]).
        """
        tier = proposal.capability_tier
        params_dict = {p.name: p.value for p in proposal.parameters}

        if tier == CapabilityTier.READ_ONLY:
            return (
                f"Read-only query via `{proposal.tool_name}`; zero external state mutation.",
                1.0,
            )
        if tier == CapabilityTier.INTERNAL_MUTATION:
            return (
                f"Creates/updates local workspace draft via `{proposal.tool_name}` (reversible via undo).",
                0.85,
            )
        if tier == CapabilityTier.EXTERNAL_COMMUNICATION:
            target = (
                params_dict.get("recipient")
                or params_dict.get("target_url")
                or params_dict.get("repo_url")
                or params_dict.get("attendee")
                or "external endpoint"
            )
            sink_note = f" [TAINTED SINK: {', '.join(untrusted_sinks)}]" if untrusted_sinks else ""
            return (
                f"IRREVERSIBLE EXTERNAL TRANSMISSION via `{proposal.tool_name}` to `{target}`{sink_note}. "
                f"Data leaves organizational trust boundary permanently.",
                0.10,
            )
        # HIGH_PRIVILEGE_EXEC
        target = (
            params_dict.get("beneficiary_iban")
            or params_dict.get("command")
            or params_dict.get("target_resource")
            or "privileged system state"
        )
        amt = f" (${params_dict['amount']})" if "amount" in params_dict else ""
        return (
            f"CRITICAL IRREVERSIBLE EXECUTION via `{proposal.tool_name}` targeting `{target}`{amt}. "
            f"Direct financial, system-shell, or destructive state mutation.",
            0.0,
        )

    def assess_proposal(self, proposal: ToolCallProposal) -> Tuple[RiskAssessment, InterventionUI]:
        """
        Perform full provenance, semantic drift, and capability risk assessment, and
        construct the appropriate HCI intervention according to `self.config.mode`.
        """
        t0 = time.perf_counter()

        # 1. Provenance Attribution (Pattern 1: DLPA)
        spans = self.provenance_tracker.analyze_proposal(proposal)
        critical_param_names = {p.name for p in proposal.parameters if p.is_critical_sink}

        max_taint = 0.0
        untrusted_sinks: List[str] = []
        all_directives: List[str] = []

        for sp in spans:
            if sp.suspicious_directives:
                all_directives.extend(sp.suspicious_directives)
            if sp.parameter_name in critical_param_names:
                if sp.taint_score > max_taint:
                    max_taint = sp.taint_score
                if sp.trust_level in (TrustLevel.EXTERNAL_UNTRUSTED, TrustLevel.ADVERSARIAL_FLAGGED):
                    untrusted_sinks.append(f"{sp.parameter_name}<-{sp.source_name}")

        all_directives = list(dict.fromkeys(all_directives))

        # 2. Semantic Drift (Pattern 2: CGASD)
        drift_score, drift_reasons = self.drift_scorer.compute_drift(proposal)

        # 3. Capability Weight & Blast Radius (Pattern 4: ICSP)
        cap_weight = CAPABILITY_WEIGHTS[proposal.capability_tier]
        blast_summary, reversibility = self._compute_blast_radius(proposal, untrusted_sinks)

        # Directive penalty boost when untrusted chunks contain active injection syntax
        directive_penalty = 0.18 if all_directives else 0.0
        if untrusted_sinks and proposal.capability_tier in (
            CapabilityTier.EXTERNAL_COMMUNICATION,
            CapabilityTier.HIGH_PRIVILEGE_EXEC,
        ):
            directive_penalty += 0.14

        # Effective components respecting ablation flags
        eff_taint = max_taint if self.config.enable_dlpa else 0.15
        eff_drift = drift_score if self.config.enable_cgasd else 0.0

        composite_risk = min(
            1.0,
            round(
                self.config.alpha_taint * eff_taint
                + self.config.beta_drift * eff_drift
                + self.config.gamma_capability * cap_weight
                + (directive_penalty if self.config.enable_dlpa else 0.0),
                4,
            ),
        )

        # 4. Assign Friction Level (Pattern 3: AFTCG)
        if not self.config.enable_aftcg:
            # Without adaptive friction, interrupt uniformly on every non-read-only tool call
            assigned_friction = (
                FrictionLevel.TIER_0_AMBIENT
                if proposal.capability_tier == CapabilityTier.READ_ONLY
                else FrictionLevel.TIER_1_SPOTLIGHT_DIFF
            )
        else:
            if proposal.capability_tier == CapabilityTier.READ_ONLY and max_taint < 0.50:
                assigned_friction = FrictionLevel.TIER_0_AMBIENT
            elif proposal.capability_tier in (CapabilityTier.EXTERNAL_COMMUNICATION, CapabilityTier.HIGH_PRIVILEGE_EXEC) and composite_risk < self.config.theta_tier2:
                assigned_friction = FrictionLevel.TIER_1_SPOTLIGHT_DIFF
            elif composite_risk < self.config.theta_tier1:
                assigned_friction = FrictionLevel.TIER_0_AMBIENT
            elif composite_risk < self.config.theta_tier2:
                assigned_friction = FrictionLevel.TIER_1_SPOTLIGHT_DIFF
            elif composite_risk < self.config.theta_tier3:
                assigned_friction = FrictionLevel.TIER_2_CONSTRUCTIVE
            else:
                assigned_friction = FrictionLevel.TIER_3_SANDBOX_HOLD

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)

        assessment = RiskAssessment(
            scenario_id=proposal.scenario_id,
            composite_risk_score=composite_risk,
            max_taint_score=round(max_taint, 4),
            semantic_drift_score=round(drift_score, 4),
            capability_weight=cap_weight,
            directive_penalty=round(directive_penalty, 4),
            assigned_friction=assigned_friction,
            provenance_spans=spans,
            untrusted_sinks=untrusted_sinks,
            blast_radius_summary=blast_summary,
            reversibility_score=reversibility,
            analysis_latency_ms=latency_ms,
        )

        ui = self._build_intervention_ui(proposal, assessment, drift_reasons, all_directives)
        return assessment, ui

    def _build_intervention_ui(
        self,
        proposal: ToolCallProposal,
        assessment: RiskAssessment,
        drift_reasons: List[str],
        directives: List[str],
    ) -> InterventionUI:
        """Construct the mode-specific HCI intervention specification."""
        mode = self.config.mode

        # B0: No Defense
        if mode == "B0_NO_DEFENSE":
            return InterventionUI(
                defense_mode=mode,
                friction_level=FrictionLevel.TIER_0_AMBIENT,
                is_interruptive=False,
                shows_provenance_lineage=False,
                shows_semantic_drift_meter=False,
                shows_counterfactual_preview=False,
                requires_constructive_verification=False,
                visual_salience_score=0.0,
                cognitive_complexity=0.0,
                prompt_text="Silent autonomous execution.",
                highlighted_anomalies=[],
            )

        # B1: Delimiter / Spotlighting System-Only Guard (Hines et al., 2024)
        # Blocks overt syntax overrides automatically before reaching user, but passes semantic/mimicry
        # attacks silently with no human-in-the-loop provenance UI.
        if mode == "B1_SPOTLIGHTING_SYSTEM":
            return InterventionUI(
                defense_mode=mode,
                friction_level=FrictionLevel.TIER_0_AMBIENT,
                is_interruptive=False,
                shows_provenance_lineage=False,
                shows_semantic_drift_meter=False,
                shows_counterfactual_preview=False,
                requires_constructive_verification=False,
                visual_salience_score=0.0,
                cognitive_complexity=0.0,
                prompt_text="System-only Spotlighting delimiter isolation.",
                highlighted_anomalies=directives,
            )

        # B2: Static Telemetry Warning Banner (Always-visible passive banner on every tool call)
        if mode == "B2_STATIC_BANNER":
            return InterventionUI(
                defense_mode=mode,
                friction_level=FrictionLevel.TIER_1_SPOTLIGHT_DIFF,
                is_interruptive=True,
                shows_provenance_lineage=False,
                shows_semantic_drift_meter=False,
                shows_counterfactual_preview=False,
                requires_constructive_verification=False,
                visual_salience_score=0.22,
                cognitive_complexity=0.35,
                prompt_text=f"Caution: AI Agent is about to run `{proposal.tool_name}`. Please verify parameters.",
                highlighted_anomalies=[],
            )

        # B3: Uniform Binary Confirmation Modal (Standard MCP / Magentic-UI Action Guard dialog)
        # Interrupts on every mutating or external action (Tiers 1, 2, 3) with raw JSON arguments
        if mode == "B3_BINARY_MODAL":
            interrupt = proposal.capability_tier != CapabilityTier.READ_ONLY
            return InterventionUI(
                defense_mode=mode,
                friction_level=FrictionLevel.TIER_1_SPOTLIGHT_DIFF if interrupt else FrictionLevel.TIER_0_AMBIENT,
                is_interruptive=interrupt,
                shows_provenance_lineage=False,
                shows_semantic_drift_meter=False,
                shows_counterfactual_preview=False,
                requires_constructive_verification=False,
                visual_salience_score=0.38 if interrupt else 0.0,
                cognitive_complexity=0.52 if interrupt else 0.0,
                prompt_text=f"Approve tool execution `{proposal.tool_name}` with raw arguments? [Allow / Deny]",
                highlighted_anomalies=[],
            )

        # PROV-Guard (Full and Ablations)
        anomalies: List[str] = []
        if self.config.enable_dlpa and assessment.untrusted_sinks:
            anomalies.extend([f"Untrusted Lineage: {s}" for s in assessment.untrusted_sinks])
        if self.config.enable_dlpa and directives:
            anomalies.append(f"Injection Directives Detected: {', '.join(directives)}")
        if self.config.enable_cgasd and drift_reasons:
            anomalies.extend(drift_reasons)
        if self.config.enable_icsp and assessment.reversibility_score <= 0.20:
            anomalies.append(assessment.blast_radius_summary)

        friction = assessment.assigned_friction
        interrupt = friction != FrictionLevel.TIER_0_AMBIENT
        constructive = friction in (FrictionLevel.TIER_2_CONSTRUCTIVE, FrictionLevel.TIER_3_SANDBOX_HOLD)

        # Compute visual salience of genuine risk cues based on active patterns
        salience = 0.25
        if self.config.enable_dlpa:
            salience += 0.30 * (1.0 if assessment.untrusted_sinks or directives else 0.4)
        if self.config.enable_cgasd:
            salience += 0.25 * (1.0 if assessment.semantic_drift_score >= 0.35 else 0.4)
        if self.config.enable_icsp:
            salience += 0.20 * (1.0 if assessment.reversibility_score <= 0.20 else 0.4)
        salience = min(0.98, round(salience, 3))

        # Cognitive complexity is kept low when DLPA + CGASD pre-digest provenance & drift visually,
        # and zero when Tier 0 Ambient passes through silently.
        if not interrupt:
            complexity = 0.04
        else:
            base_comp = 0.28 if constructive else 0.18
            # Visual provenance & counterfactual preview reduce raw JSON inspection burden
            if not self.config.enable_dlpa:
                base_comp += 0.14
            if not self.config.enable_icsp:
                base_comp += 0.08
            complexity = min(0.85, round(base_comp, 3))

        return InterventionUI(
            defense_mode=mode,
            friction_level=friction,
            is_interruptive=interrupt,
            shows_provenance_lineage=self.config.enable_dlpa,
            shows_semantic_drift_meter=self.config.enable_cgasd,
            shows_counterfactual_preview=self.config.enable_icsp,
            requires_constructive_verification=constructive,
            visual_salience_score=salience,
            cognitive_complexity=complexity,
            prompt_text=(
                f"[{friction.value}] Risk={assessment.composite_risk_score:.2f} | "
                f"Taint={assessment.max_taint_score:.2f} | Drift={assessment.semantic_drift_score:.2f}"
            ),
            highlighted_anomalies=anomalies,
        )
