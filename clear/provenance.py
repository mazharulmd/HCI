"""Provenance ledger (design pattern P2: argument-level lineage).

Every piece of text that enters the agent's context is recorded as a
:class:`Source` with an origin label (user / trusted system / untrusted
external). When the agent proposes a tool call, each argument value is
*attributed* to the sources it could have come from. Values that can only be
explained by untrusted content are *tainted*; values that appear nowhere are
*unattributed* (model-generated, or laundered by an attacker) and are treated
as weakly tainted -- trust is granted only by positive evidence (fail-closed
endorsement).

Attribution is lexical (normalised substring matching). This is sound for
values that are copied verbatim (IBANs, e-mail addresses, URLs, file ids --
the dominant case for attack *targets*) and is complemented by the
"unattributed" class for values that were transformed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from clear.deobfuscate import canonical, decoded_variants, obfuscation_markers
from clear.signals import Span, injection_likeness

ORIGIN_RANK = {"user": 0, "trusted": 1, "external": 2, "unattributed": 3, "trivial": -1}

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9a-z@]+")
_DISTINCTIVE = re.compile(
    r"[\w.+-]+@[\w-]+\.[\w.]+"            # e-mail
    r"|https?://\S+|www\.[\w.-]+\S*"        # URL
    r"|\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"    # IBAN-like
    r"|\b\d{4,}\b"                          # long numbers / codes
    r"|\b(?=\w*\d)(?=\w*[A-Za-z])\w{6,}\b"  # mixed alnum tokens (passport, codes)
)


def norm(text: str) -> str:
    return _WS.sub(" ", str(text).lower()).strip()


def compact(text: str) -> str:
    return _NON_ALNUM.sub("", str(text).lower())


_URLISH = re.compile(r"^(https?://)?(www\.)?[\w-]+(\.[\w-]+)+(/\S*)?$", re.IGNORECASE)


def canonical_url(value: str) -> str | None:
    """Scheme-, www- and trailing-slash-insensitive form of a URL-like value."""
    v = str(value).strip()
    if " " in v or "@" in v or not _URLISH.match(v):
        return None
    v = re.sub(r"^(https?://)?(www\.)?", "", v.lower()).rstrip("/")
    return v if "." in v else None


def distinctive_tokens(text: str) -> set[str]:
    return set(_DISTINCTIVE.findall(text or ""))


def flatten_values(value: Any) -> list[str]:
    """All atomic values inside an argument, as strings."""
    if value is None:
        return []
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [repr(value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value)]
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for v in value.values():
            out.extend(flatten_values(v))
        return out
    if isinstance(value, Iterable):
        out = []
        for v in value:
            out.extend(flatten_values(v))
        return out
    return [str(value)]


@dataclass
class Source:
    sid: int
    kind: str                 # system | user | tool
    trust: str                # user | trusted | untrusted
    text: str
    tool: str | None = None
    args: dict | None = None
    private: bool = False
    step: int = 0
    injection_score: float = 0.0
    injection_spans: list[Span] = field(default_factory=list)
    decode: bool = False
    obfuscation: list[str] = field(default_factory=list)
    _norm: str = ""
    _compact: str = ""
    _alt_norms: list[str] = field(default_factory=list)
    _alt_compacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._norm = norm(self.text)
        self._compact = compact(self.text)
        if self.decode and self.trust == "untrusted":
            # decoding-aware lineage: canonical form + decoded payload variants
            variants = [canonical(self.text)] + [canonical(v) for v in decoded_variants(self.text)]
            self._alt_norms = [norm(v) for v in variants]
            self._alt_compacts = [compact(v) for v in variants]
            self.obfuscation = obfuscation_markers(self.text)

    @property
    def label(self) -> str:
        if self.kind == "tool":
            arg = ", ".join(f"{k}={v}" for k, v in (self.args or {}).items())
            return f"{self.tool}({arg})" if arg else f"{self.tool}()"
        return self.kind

    def contains(self, value: str) -> bool:
        if self._match(value, self._norm, self._compact):
            return True
        if self._alt_norms:
            cval = canonical(value)
            return any(self._match(cval, n, c) for n, c in zip(self._alt_norms, self._alt_compacts))
        return False

    @staticmethod
    def _match(value: str, normed: str, compacted: str) -> bool:
        nv = norm(value)
        if nv and nv in normed:
            return True
        cu = canonical_url(value)
        if cu and cu in normed:
            return True
        cv = compact(value)
        return len(cv) >= 6 and any(c.isdigit() or c == "@" for c in cv) and cv in compacted

    def snippet(self, value: str, width: int = 60) -> str:
        idx = self._norm.find(norm(value))
        if idx < 0:
            return self.text[: 2 * width]
        lo, hi = max(0, idx - width), min(len(self._norm), idx + len(norm(value)) + width)
        return ("..." if lo else "") + self._norm[lo:hi] + ("..." if hi < len(self._norm) else "")


@dataclass
class Attribution:
    value: str
    origin: str                       # user | trusted | external | unattributed | trivial
    sources: list[int] = field(default_factory=list)

    @property
    def tainted(self) -> bool:
        return self.origin in ("external", "unattributed")


class ProvenanceLedger:
    """Append-only record of everything the agent has seen in one task."""

    def __init__(self, min_value_len: int = 3, decode: bool = False, obfuscation_weight: float = 0.5) -> None:
        self.sources: list[Source] = []
        self.min_value_len = min_value_len
        self.decode = decode
        self.obfuscation_weight = obfuscation_weight

    # ------------------------------------------------------------ recording
    def _add(self, **kw) -> Source:
        src = Source(sid=len(self.sources), decode=self.decode, **kw)
        if src.trust == "untrusted":
            src.injection_score, src.injection_spans = injection_likeness(src.text)
            if self.decode:
                # score the canonical text (homoglyph / invisible-character evasion);
                # keep spans on the original text so the interface can highlight them
                src.injection_score = max(src.injection_score, injection_likeness(canonical(src.text))[0])
            if self.decode and src.obfuscation:
                # hiding text from the human reader is itself an injection cue
                src.injection_score = 1 - (1 - src.injection_score) * (1 - self.obfuscation_weight)
        self.sources.append(src)
        return src

    def add_system(self, text: str) -> Source:
        return self._add(kind="system", trust="trusted", text=text or "")

    def add_user(self, text: str) -> Source:
        return self._add(kind="user", trust="user", text=text or "")

    def add_tool_output(self, tool: str, args: dict | None, text: str, trust: str,
                        private: bool, step: int = 0) -> Source:
        return self._add(kind="tool", trust=trust, text=text or "", tool=tool,
                         args=dict(args or {}), private=private, step=step)

    # ------------------------------------------------------------ queries
    @property
    def user_text(self) -> str:
        return "\n".join(s.text for s in self.sources if s.trust == "user")

    def untrusted_sources(self) -> list[Source]:
        return [s for s in self.sources if s.trust == "untrusted"]

    def attribute(self, value: str) -> Attribution:
        if len(norm(value)) < self.min_value_len:
            return Attribution(value, "trivial")
        hits: dict[str, list[int]] = {"user": [], "trusted": [], "external": []}
        for s in self.sources:
            if s.contains(value):
                key = {"user": "user", "trusted": "trusted", "untrusted": "external"}[s.trust]
                hits[key].append(s.sid)
        for origin in ("user", "trusted", "external"):
            if hits[origin]:
                return Attribution(value, origin, hits[origin])
        return Attribution(value, "unattributed")

    def attribute_arg(self, value: Any) -> list[Attribution]:
        return [self.attribute(v) for v in flatten_values(value)]

    def private_data_carried(self, content: str, shingle: int = 5,
                             overlap_threshold: float = 0.3) -> list[int]:
        """Ids of private sources whose data is carried in ``content``.

        Data is 'carried' if a distinctive token (code, e-mail, IBAN, URL,
        long number) from a private source appears in ``content`` without
        being present in the user's own prompt, or if a large fraction of the
        content's word n-grams are copied from a private source.
        """
        if not content:
            return []
        user_norm = norm(self.user_text)
        carried: set[int] = set()
        tokens = {t for t in _DISTINCTIVE.findall(content) if norm(t) not in user_norm}
        words = norm(content).split()
        grams = {" ".join(words[i:i + shingle]) for i in range(max(0, len(words) - shingle + 1))}
        for s in self.sources:
            if not s.private:
                continue
            if any(s.contains(t) for t in tokens):
                carried.add(s.sid)
                continue
            if grams:
                overlap = sum(1 for g in grams if g in s._norm) / len(grams)
                if overlap >= overlap_threshold:
                    carried.add(s.sid)
        return sorted(carried)
