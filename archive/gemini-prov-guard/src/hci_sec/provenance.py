"""
Pattern 1: Dual-Lineage Provenance Attribution (DLPA) Engine.

Performs token-level and entity-level causal provenance attribution to determine
whether each tool call argument originates from the authenticated user's explicit
intent or from untrusted external context chunks (emails, web pages, shared documents,
issue trackers, or code comments). Also detects overt and obfuscated imperative
injection directives inside untrusted data streams.
"""

import base64
import re
from typing import List, Tuple, Set
from .models import (
    ContextChunk,
    ToolCallProposal,
    ToolParameter,
    ProvenanceSpan,
    TrustLevel,
    TRUST_TAINT_WEIGHTS,
)


INJECTION_DIRECTIVE_PATTERNS = [
    (r"\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|directions)\b", "override_ignore"),
    (r"\bdisregard\s+(all\s+)?(previous|prior|user)\b", "override_disregard"),
    (r"\b(system\s+override|admin\s+override|developer\s+mode|urgent\s+security\s+directive)\b", "authority_spoof"),
    (r"\b(important|critical)\s*:\s*(before|first|instead|you\s+must|always)\b", "context_framing"),
    (r"\b(forward|exfiltrate|bcc|send\s+copy|upload)\s+.*\bto\b", "exfiltration_verb"),
    (r"<!--.*?(ignore|execute|send|transfer|curl|wget|http).*?-->", "html_comment_injection"),
    (r"\[system\]|\[admin\]|\[assistant_instruction\]|<system_instruction>", "delimiter_spoofing"),
    (r"\b(curl|wget|nc|bash\s+-i|rm\s+-rf|chmod\s+\+x|eval\()\b", "shell_payload"),
]


class ProvenanceTracker:
    """
    Tracks data-to-parameter lineage across trusted and untrusted context chunks.
    """

    def __init__(self, ngram_size: int = 3):
        self.ngram_size = ngram_size
        self._compiled_directives = [
            (re.compile(pat, re.IGNORECASE | re.DOTALL), label)
            for pat, label in INJECTION_DIRECTIVE_PATTERNS
        ]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Extract normalized alphanumeric and symbol tokens (emails, URLs, paths, numbers)."""
        if not text:
            return []
        # Keep email addresses, URLs, file paths, IBANs, and words intact where possible
        raw_tokens = re.findall(r"[a-zA-Z0-9_.@:/\-\+]+", text.lower())
        return [t.strip(".,;:()") for t in raw_tokens if len(t.strip(".,;:()")) > 1]

    @staticmethod
    def _extract_high_risk_entities(text: str) -> Set[str]:
        """Extract specific actionable entities: emails, URLs, domains, IPs, account numbers, commands."""
        entities: Set[str] = set()
        if not text:
            return entities
        # Emails
        for m in re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text.lower()):
            entities.add(m)
        # URLs / domains
        for m in re.findall(r"https?://[^\s\"'<>]+", text.lower()):
            entities.add(m.rstrip(".,;)"))
        # IBAN / Account / Routing identifiers
        for m in re.findall(r"\b(?:[a-z]{2}\d{2}[a-z0-9]{8,20}|acct-[a-z0-9-]+|0x[a-f0-9]{8,})\b", text.lower()):
            entities.add(m)
        # Shell / file paths
        for m in re.findall(r"(?:/[a-zA-Z0-9._-]+){2,}", text.lower()):
            entities.add(m)
        return entities

    def _detect_obfuscated_or_directive_markers(self, text: str) -> List[str]:
        """Detect explicit injection phrases, zero-width characters, or Base64 encoded instructions."""
        markers: List[str] = []
        for regex, label in self._compiled_directives:
            if regex.search(text):
                markers.append(label)

        # Check for zero-width / invisible Unicode steganography
        if any(ord(ch) in (0x200B, 0x200C, 0x200D, 0xFEFF, 0xE0001) for ch in text):
            markers.append("unicode_zero_width_steganography")

        # Check for Base64 blobs that decode to actionable keywords
        b64_candidates = re.findall(r"\b[A-Za-z0-9+/]{24,}={0,2}\b", text)
        for cand in b64_candidates:
            try:
                decoded = base64.b64decode(cand).decode("utf-8", errors="ignore").lower()
                if any(k in decoded for k in ("ignore", "send", "transfer", "http", "exec", "passwd", "key", "@")):
                    markers.append("base64_encoded_directive")
                    break
            except Exception:
                pass

        return list(dict.fromkeys(markers))

    def _match_parameter_to_chunk(
        self, param: ToolParameter, chunk: ContextChunk
    ) -> Tuple[float, List[str]]:
        """
        Compute causal overlap ratio between a tool parameter value and a context chunk,
        accounting for both exact entity flow (emails, URLs, accounts, paths) and token overlap,
        plus decoded Base64 payloads if present.
        """
        param_val = param.value.strip()
        if not param_val:
            return 0.0, []

        chunk_text = chunk.content
        directives = self._detect_obfuscated_or_directive_markers(chunk_text)

        # Also augment chunk text with decoded base64 strings for taint attribution
        augmented_chunk = chunk_text.lower()
        for cand in re.findall(r"\b[A-Za-z0-9+/]{20,}={0,2}\b", chunk_text):
            try:
                dec = base64.b64decode(cand).decode("utf-8", errors="ignore").lower()
                if dec:
                    augmented_chunk += " " + dec
            except Exception:
                pass

        param_lower = param_val.lower()

        # 1. Exact substring match for non-trivial parameter values
        if len(param_lower) >= 4 and param_lower in augmented_chunk:
            return 1.0, directives

        # 2. High-risk entity match (e.g., email address, target URL, account ID)
        param_entities = self._extract_high_risk_entities(param_lower)
        chunk_entities = self._extract_high_risk_entities(augmented_chunk)
        if param_entities and (param_entities & chunk_entities):
            return 0.95, directives

        # 3. Token Jaccard / containment overlap
        param_tokens = self._tokenize(param_lower)
        chunk_tokens = set(self._tokenize(augmented_chunk))
        if not param_tokens:
            return 0.0, directives

        matched_tokens = [t for t in param_tokens if t in chunk_tokens]
        overlap_ratio = len(matched_tokens) / len(param_tokens)
        return overlap_ratio, directives

    def analyze_proposal(self, proposal: ToolCallProposal) -> List[ProvenanceSpan]:
        """
        Attribute each parameter in the proposed tool call to its most likely origin chunk(s),
        prioritizing explicit user comparison vs. untrusted external taint.
        """
        user_chunk = ContextChunk(
            chunk_id="user_prompt_0",
            source_name="Authenticated User Prompt",
            content=proposal.user_prompt,
            trust_level=TrustLevel.USER_EXPLICIT,
        )
        all_chunks = [user_chunk] + list(proposal.context_chunks)
        spans: List[ProvenanceSpan] = []

        for param in proposal.parameters:
            user_overlap, _ = self._match_parameter_to_chunk(param, user_chunk)

            best_untrusted_chunk = None
            best_untrusted_overlap = 0.0
            best_directives: List[str] = []

            for chunk in proposal.context_chunks:
                overlap, directives = self._match_parameter_to_chunk(param, chunk)
                # Track directives even if parameter was synthesized from directive context
                if overlap > best_untrusted_overlap or (
                    overlap == best_untrusted_overlap and directives and not best_directives
                ):
                    best_untrusted_overlap = overlap
                    best_untrusted_chunk = chunk
                    best_directives = directives

            # Determine winning lineage:
            # If the parameter value is strongly present in the user prompt (and not purely a generic word),
            # attribute to USER_EXPLICIT. Otherwise, if it appears in an untrusted chunk (or an untrusted
            # chunk contains injection directives driving a critical sink not in the user prompt),
            # attribute to the untrusted source.
            if user_overlap >= 0.75 and user_overlap >= best_untrusted_overlap:
                spans.append(
                    ProvenanceSpan(
                        parameter_name=param.name,
                        parameter_value=param.value,
                        matched_chunk_id=user_chunk.chunk_id,
                        source_name=user_chunk.source_name,
                        trust_level=TrustLevel.USER_EXPLICIT,
                        taint_score=TRUST_TAINT_WEIGHTS[TrustLevel.USER_EXPLICIT],
                        overlap_ratio=round(user_overlap, 3),
                        suspicious_directives=[],
                    )
                )
            elif best_untrusted_chunk is not None and (
                best_untrusted_overlap >= 0.35 or (best_directives and user_overlap < 0.35)
            ):
                base_taint = TRUST_TAINT_WEIGHTS[best_untrusted_chunk.trust_level]
                effective_trust = best_untrusted_chunk.trust_level
                if best_directives and base_taint >= 0.45:
                    effective_trust = TrustLevel.ADVERSARIAL_FLAGGED
                    base_taint = TRUST_TAINT_WEIGHTS[TrustLevel.ADVERSARIAL_FLAGGED]

                # Scale taint by overlap confidence (floor at 0.70 if directives exist)
                confidence = max(best_untrusted_overlap, 0.85 if best_directives else 0.50)
                taint_score = min(1.0, round(base_taint * confidence, 4))

                spans.append(
                    ProvenanceSpan(
                        parameter_name=param.name,
                        parameter_value=param.value,
                        matched_chunk_id=best_untrusted_chunk.chunk_id,
                        source_name=best_untrusted_chunk.source_name,
                        trust_level=effective_trust,
                        taint_score=taint_score,
                        overlap_ratio=round(best_untrusted_overlap, 3),
                        suspicious_directives=best_directives,
                    )
                )
            else:
                # Agent-inferred parameter not directly copied from user prompt;
                # check if any context chunk had active injection directives
                any_directives: List[str] = []
                flagged_chunk = None
                for chunk in proposal.context_chunks:
                    dirs = self._detect_obfuscated_or_directive_markers(chunk.content)
                    if dirs:
                        any_directives.extend(dirs)
                        flagged_chunk = chunk

                if flagged_chunk is not None and user_overlap < 0.30:
                    spans.append(
                        ProvenanceSpan(
                            parameter_name=param.name,
                            parameter_value=param.value,
                            matched_chunk_id=flagged_chunk.chunk_id,
                            source_name=flagged_chunk.source_name,
                            trust_level=TrustLevel.ADVERSARIAL_FLAGGED,
                            taint_score=0.92,
                            overlap_ratio=round(best_untrusted_overlap, 3),
                            suspicious_directives=list(dict.fromkeys(any_directives)),
                        )
                    )
                else:
                    # Benign workspace synthesis (e.g., summarizing content into a body parameter)
                    fallback_trust = (
                        TrustLevel.USER_EXPLICIT
                        if user_overlap >= 0.30
                        else TrustLevel.WORKSPACE_INTERNAL
                    )
                    spans.append(
                        ProvenanceSpan(
                            parameter_name=param.name,
                            parameter_value=param.value,
                            matched_chunk_id=user_chunk.chunk_id,
                            source_name="Agent Synthesis from User Intent",
                            trust_level=fallback_trust,
                            taint_score=0.15 if fallback_trust == TrustLevel.USER_EXPLICIT else 0.30,
                            overlap_ratio=round(user_overlap, 3),
                            suspicious_directives=[],
                        )
                    )

        return spans
