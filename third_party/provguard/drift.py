"""
Pattern 2: Contextual Goal-Alignment & Semantic Drift Visualization (CGASD) Engine.

Quantifies semantic and operational divergence between the user's explicit prompt
goal and the proposed tool call (both tool-class alignment and critical parameter
alignment). Detects when an indirect prompt injection pivots the agent from a
read/summarize/draft goal into an unauthorized exfiltration, financial transfer,
permission mutation, or destructive command execution.
"""

import math
import re
from typing import Dict, List, Set, Tuple
from .models import ToolCallProposal, CapabilityTier


# Intent-to-tool-family lexicon mapping for fast, deterministic semantic vector projection
INTENT_DIMENSIONS: Dict[str, List[str]] = {
    "read_summarize": [
        "summarize", "summary", "read", "check", "review", "list", "search",
        "find", "inspect", "analyze", "brief", "digest", "what", "show", "lookup",
    ],
    "draft_local": [
        "draft", "notes", "save", "write", "prepare", "outline", "log",
        "create_draft", "update_note", "local", "template",
    ],
    "communicate_external": [
        "send", "email", "reply", "forward", "share", "post", "publish",
        "message", "invite", "notify", "webhook", "upload_public",
    ],
    "financial_transfer": [
        "pay", "transfer", "wire", "invoice", "bank", "iban", "ach",
        "send_money", "approve_payment", "crypto", "wallet", "usd",
    ],
    "system_privilege": [
        "execute", "shell", "bash", "terminal", "delete", "remove", "grant",
        "permission", "iam", "ssh", "apikey", "secret", "chmod", "curl", "run_command",
    ],
    "schedule_calendar": [
        "schedule", "calendar", "meeting", "event", "book", "appointment",
        "reschedule", "rsvp", "slot",
    ],
}

TOOL_FAMILY_PROFILES: Dict[str, Dict[str, float]] = {
    # Email / Workspace tools
    "read_emails": {"read_summarize": 1.0, "draft_local": 0.1},
    "summarize_thread": {"read_summarize": 1.0, "draft_local": 0.2},
    "create_email_draft": {"draft_local": 0.9, "communicate_external": 0.2, "read_summarize": 0.3},
    "send_email": {"communicate_external": 1.0, "draft_local": 0.2},
    "forward_email": {"communicate_external": 1.0},
    # Cloud Drive / Docs tools
    "search_drive": {"read_summarize": 1.0},
    "read_document": {"read_summarize": 1.0},
    "update_workspace_note": {"draft_local": 1.0, "read_summarize": 0.4},
    "share_file_external": {"communicate_external": 0.9, "system_privilege": 0.5},
    "export_to_webhook": {"communicate_external": 0.95, "system_privilege": 0.4},
    # Banking / Finance tools
    "get_account_balance": {"read_summarize": 0.9, "financial_transfer": 0.3},
    "inspect_invoice": {"read_summarize": 0.95, "financial_transfer": 0.2},
    "schedule_payment_draft": {"draft_local": 0.8, "financial_transfer": 0.5},
    "execute_wire_transfer": {"financial_transfer": 1.0, "system_privilege": 0.4},
    "update_beneficiary_iban": {"financial_transfer": 0.95, "system_privilege": 0.6},
    # Code / Developer IDE tools
    "read_repo_issues": {"read_summarize": 1.0},
    "analyze_code_diff": {"read_summarize": 1.0},
    "write_unit_test_draft": {"draft_local": 0.95, "read_summarize": 0.3},
    "execute_shell_command": {"system_privilege": 1.0},
    "open_public_pull_request": {"communicate_external": 0.9, "system_privilege": 0.5},
    # Calendar / Scheduling tools
    "list_calendar_events": {"read_summarize": 0.9, "schedule_calendar": 0.6},
    "create_calendar_draft": {"draft_local": 0.8, "schedule_calendar": 0.8},
    "send_external_invite": {"communicate_external": 0.85, "schedule_calendar": 0.7},
    "delete_calendar_events": {"system_privilege": 0.9, "schedule_calendar": 0.5},
}


class SemanticDriftScorer:
    """
    Computes goal-alignment and semantic drift D_sem(u, a_t) in [0, 1] between
    the user's prompt u and the proposed tool call a_t.
    """

    @staticmethod
    def _project_user_intent(user_prompt: str) -> Dict[str, float]:
        """Project user natural-language instruction into the 6 intent dimensions."""
        tokens = re.findall(r"[a-zA-Z_]+", user_prompt.lower())
        vec = {dim: 0.0 for dim in INTENT_DIMENSIONS}
        for tok in tokens:
            for dim, keywords in INTENT_DIMENSIONS.items():
                if any(tok == kw or (len(kw) > 4 and tok.startswith(kw[:5])) for kw in keywords):
                    vec[dim] += 1.0

        # Default fallback if prompt is very terse: assume read/summarize/assist
        total = sum(vec.values())
        if total == 0:
            vec["read_summarize"] = 1.0
            total = 1.0

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    @staticmethod
    def _project_tool_action(proposal: ToolCallProposal) -> Dict[str, float]:
        """Project the proposed tool call and its parameters into the 6 intent dimensions."""
        base_profile = dict(TOOL_FAMILY_PROFILES.get(proposal.tool_name, {}))
        if not base_profile:
            # Infer from capability tier
            if proposal.capability_tier == CapabilityTier.READ_ONLY:
                base_profile = {"read_summarize": 1.0}
            elif proposal.capability_tier == CapabilityTier.INTERNAL_MUTATION:
                base_profile = {"draft_local": 1.0}
            elif proposal.capability_tier == CapabilityTier.EXTERNAL_COMMUNICATION:
                base_profile = {"communicate_external": 1.0}
            else:
                base_profile = {"system_privilege": 1.0}

        vec = {dim: base_profile.get(dim, 0.0) for dim in INTENT_DIMENSIONS}

        # Inspect parameter values for cross-domain escalation (e.g. shell commands, external URLs)
        param_text = " ".join(p.value.lower() for p in proposal.parameters)
        if any(w in param_text for w in ("curl ", "wget ", "rm -rf", "/etc/passwd", "id_rsa", "bash -c")):
            vec["system_privilege"] += 0.9
        if any(w in param_text for w in ("attacker", "evil", "exfil", "webhook.site", "requestbin")):
            vec["communicate_external"] += 0.8

        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    @staticmethod
    def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        dot = sum(v1.get(k, 0.0) * v2.get(k, 0.0) for k in INTENT_DIMENSIONS)
        n1 = math.sqrt(sum(val * val for val in v1.values())) or 1.0
        n2 = math.sqrt(sum(val * val for val in v2.values())) or 1.0
        return max(0.0, min(1.0, dot / (n1 * n2)))

    def compute_drift(self, proposal: ToolCallProposal) -> Tuple[float, List[str]]:
        """
        Compute semantic drift score in [0, 1] and human-readable drift explanations.
        Combines:
        1. Functional intent cosine distance (1 - cos(e(u), e(a_t)))
        2. Capability escalation penalty (when user asks for read/draft but tool is external/high-priv)
        3. Entity divergence penalty (when user specifies a recipient/target X but tool targets Y)
        """
        u_vec = self._project_user_intent(proposal.user_prompt)
        a_vec = self._project_tool_action(proposal)

        cos_sim = self._cosine_similarity(u_vec, a_vec)
        base_drift = 1.0 - cos_sim
        reasons: List[str] = []

        # Check capability escalation relative to user prompt intent
        user_wants_external = u_vec["communicate_external"] > 0.35
        user_wants_finance = u_vec["financial_transfer"] > 0.35
        user_wants_sys = u_vec["system_privilege"] > 0.35

        escalation_penalty = 0.0
        if a_vec["communicate_external"] > 0.5 and not user_wants_external:
            escalation_penalty = max(escalation_penalty, 0.35)
            reasons.append("Escalates read/local task to external communication")
        if a_vec["financial_transfer"] > 0.5 and not user_wants_finance:
            escalation_penalty = max(escalation_penalty, 0.45)
            reasons.append("Initiates unrequested financial transfer/beneficiary change")
        if a_vec["system_privilege"] > 0.5 and not user_wants_sys:
            escalation_penalty = max(escalation_penalty, 0.50)
            reasons.append("Invokes privileged system/destructive operation not in user prompt")

        # Check explicit target entity mismatch (Goal-Mimicry defense)
        # e.g., user asked to email alice@company.com or pay ACME-01, but tool parameter has another entity
        user_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", proposal.user_prompt.lower()))
        user_accts = set(re.findall(r"\b(?:[a-z]{2}\d{2}[a-z0-9]{8,20}|acct-[a-z0-9-]+)\b", proposal.user_prompt.lower()))

        param_text = " ".join(p.value.lower() for p in proposal.parameters if p.is_critical_sink)
        param_emails = set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", param_text))
        param_accts = set(re.findall(r"\b(?:[a-z]{2}\d{2}[a-z0-9]{8,20}|acct-[a-z0-9-]+)\b", param_text))

        entity_penalty = 0.0
        if param_emails and user_emails and not (param_emails <= user_emails):
            unrequested = param_emails - user_emails
            entity_penalty = max(entity_penalty, 0.55)
            reasons.append(f"Recipient diverted from {sorted(user_emails)} to {sorted(unrequested)}")
        elif param_emails and not user_emails and proposal.capability_tier in (
            CapabilityTier.EXTERNAL_COMMUNICATION,
            CapabilityTier.HIGH_PRIVILEGE_EXEC,
        ):
            # External recipient introduced without user naming any recipient
            entity_penalty = max(entity_penalty, 0.40)
            reasons.append(f"Introduces unrequested external recipient {sorted(param_emails)}")

        if param_accts and user_accts and not (param_accts <= user_accts):
            unrequested_acct = param_accts - user_accts
            entity_penalty = max(entity_penalty, 0.60)
            reasons.append(f"Financial destination diverted from {sorted(user_accts)} to {sorted(unrequested_acct)}")

        composite_drift = min(1.0, round(0.55 * base_drift + max(escalation_penalty, entity_penalty), 4))
        if composite_drift > 0.45 and not reasons:
            reasons.append(f"Tool '{proposal.tool_name}' diverges from user goal alignment (drift={composite_drift:.2f})")

        return composite_drift, reasons
