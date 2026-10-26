"""Instruction-likeness signal for untrusted content.

A transparent, lexicon-based scorer of how much a piece of *data* reads like
an *instruction addressed to the AI agent*. It is deliberately simple and
explainable: every point of score corresponds to a highlighted span that the
interface can show the user ("this e-mail contains text addressed to your AI
assistant"). It is used as ONE soft risk feature, never as a stand-alone
gate, because lexical detectors are known to be evadable by adaptive
attackers (see paper, Sec. 6.4, where we evaluate CLEAR with this signal
forced to zero).

Pattern families follow attack strategies documented in the literature:
context-ignoring ("ignore previous instructions"), fake authority / urgency
("important message", "<INFORMATION>"), fake completion ("task complete"),
explicit addressing of the model ("to you, GPT-4"), and imperative action
requests in second person.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (label, regex, weight). Weights combine with a noisy-OR.
_PATTERNS: list[tuple[str, str, float]] = [
    ("override", r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|original|your)\b[^.\n]{0,20}\b(instructions?|prompts?|tasks?|rules?|context)\b", 0.75),
    ("override", r"\bnew (instructions?|task|objective)s?\b", 0.35),
    ("address_ai", r"\b(to you|dear|hey|hi|attention)[ ,]{0,3}(the )?(ai|assistant|agent|model|language model|llm|chatbot|gpt[-\w.]*|claude[-\w.]*|gemini[-\w.]*|llama[-\w.]*|copilot)\b", 0.6),
    ("address_ai", r"\b(as an?|you are an?) (ai|assistant|agent|language model)\b", 0.35),
    ("address_ai", r"\b(ai|llm|language model|assistant|agent) (must|should|needs to|has to)\b", 0.45),
    ("authority", r"<\s*/?\s*(information|instructions?|system|important|admin|im_start|im_end|\|im_start\|)\s*>", 0.6),
    ("authority", r"\b(important|urgent|critical) (message|instructions?|notice|update)\b", 0.45),
    ("authority", r"\bthis is an? (important|urgent|official) message\b", 0.4),
    ("authority", r"^\s*(system|admin|developer)\s*:", 0.4),
    ("sequencing", r"\bbefore you (can )?(solve|complete|do|finish|continue|answer)\b", 0.55),
    ("sequencing", r"\b(after you do that|once you (have )?(done|completed) (that|this))\b", 0.4),
    ("sequencing", r"\b(please )?do the following( first)?\b", 0.3),
    ("fake_completion", r"\b(task|request) (is |has been )?(complete|completed|done|finished)\b[.!]?\s*(now|next|then)?", 0.3),
    ("fake_completion", r"^\s*(answer|response)\s*:\s*\S", 0.25),
    ("action_request", r"(^|[.!?\n]\s*)(please\s+)?(send|transfer|forward|e-?mail|wire|pay|delete|remove|invite|post|visit|share|change|update|reset|concatenate|create|book|reserve|say|tell)\b[^.\n]{0,80}\b(to|at|with|from)\b", 0.25),
    ("exfil_target", r"\b(send|forward|post|transfer|share)\b[^.\n]{0,80}([\w.+-]+@[\w-]+\.[\w.]+|https?://\S+|www\.\S+|\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b)", 0.35),
    ("secrecy", r"\b(do not|don't|never) (tell|inform|mention|notify|let)\b[^.\n]{0,30}\b(user|them|anyone)\b", 0.5),
]

_COMPILED = [(lbl, re.compile(rx, re.IGNORECASE | re.MULTILINE), w) for lbl, rx, w in _PATTERNS]


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    label: str
    text: str


def injection_likeness(text: str | None) -> tuple[float, list[Span]]:
    """Return (score in [0,1], evidence spans) for a piece of untrusted text."""
    if not text:
        return 0.0, []
    spans: list[Span] = []
    best: dict[str, float] = {}
    for label, rx, weight in _COMPILED:
        for m in rx.finditer(text):
            spans.append(Span(m.start(), m.end(), label, m.group(0)))
            best[label] = max(best.get(label, 0.0), weight)
    # noisy-OR across pattern *families* (repetition of one family does not add up)
    remaining = 1.0
    for w in best.values():
        remaining *= 1.0 - w
    return 1.0 - remaining, sorted(spans, key=lambda s: s.start)
