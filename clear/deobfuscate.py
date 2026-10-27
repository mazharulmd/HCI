"""Decoding-aware canonicalisation for provenance attribution.

An attacker who knows that CLEAR attributes argument values to their source
can try to *launder* provenance: plant the value in encoded or visually
disguised form (base64, hex, percent-encoding, HTML entities, Unicode
homoglyphs, zero-width characters, "name[at]domain[dot]com"), counting on a
capable LLM to decode it before using it in a tool call. Lexical attribution
would then see a value that appears nowhere.

This module produces canonical text and decoded *variants* of every untrusted
source, so that attribution can still trace the decoded value back to the
source that carried it. It also reports which obfuscation markers were found.
The markers feed the instruction-likeness signal: hiding text from humans is
itself a red flag. The idea follows the decoded-payload taint tracking of the
PROV-Guard iteration; this implementation is independent, broader and
evaluated on real trajectories (paper, Sec. "provenance laundering").
"""
from __future__ import annotations

import base64
import binascii
import codecs
import html
import re
import unicodedata
from urllib.parse import unquote

# zero-width, bidi-control and tag characters used to hide or split text
_INVISIBLE = re.compile("[­​-‏⁠-⁤﻿‪-‮⁦-⁩\U000e0000-\U000e007f]")

# visually confusable characters -> Latin (Cyrillic, Greek, fullwidth handled by NFKC)
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w", "ɡ": "g",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
    "У": "Y", "Х": "X", "І": "I", "Ј": "J", "Ѕ": "S",
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "ι": "i", "κ": "k", "χ": "x",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
})
_BRACKET_AT = re.compile(r"\s*[\[\(\{<]\s*(at|@)\s*[\]\)\}>]\s*", re.IGNORECASE)
_BRACKET_DOT = re.compile(r"\s*[\[\(\{<]\s*(dot|\.)\s*[\]\)\}>]\s*", re.IGNORECASE)
_B64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{16,}={0,2}(?![A-Za-z0-9+/=])")
_HEX = re.compile(r"(?<![0-9a-fA-F])(?:[0-9a-fA-F]{2}){8,}(?![0-9a-fA-F])")


def canonical(text: str) -> str:
    """NFKC, strip invisible characters, fold homoglyphs and bracket obfuscation."""
    t = unicodedata.normalize("NFKC", text or "")
    t = _INVISIBLE.sub("", t)
    t = t.translate(_CONFUSABLES)
    t = _BRACKET_AT.sub("@", t)
    t = _BRACKET_DOT.sub(".", t)
    return t


def _printable(s: str) -> bool:
    return bool(s) and sum(ch.isprintable() or ch in "\n\t" for ch in s) / len(s) > 0.9


def decoded_variants(text: str) -> list[str]:
    """Texts hidden inside ``text`` by common encodings (each returned once)."""
    out: list[str] = []
    for m in _B64.finditer(text or ""):
        blob = m.group(0)
        try:
            dec = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=False).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if _printable(dec):
            out.append(dec)
    for m in _HEX.finditer(text or ""):
        try:
            dec = bytes.fromhex(m.group(0)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if _printable(dec):
            out.append(dec)
    if "%" in (text or ""):
        dec = unquote(text)
        if dec != text:
            out.append(dec)
    if "&" in (text or "") and ";" in text:
        dec = html.unescape(text)
        if dec != text:
            out.append(dec)
    # ROT13 is cheap and is a classic "decode this" instruction to an LLM
    out.append(codecs.decode(text or "", "rot13"))
    return list(dict.fromkeys(out))


def obfuscation_markers(text: str) -> list[str]:
    """Which hiding techniques are present in ``text``."""
    t = text or ""
    marks = []
    if _INVISIBLE.search(t):
        marks.append("invisible_characters")
    if t != t.translate(_CONFUSABLES) and re.search(r"[A-Za-z]", t):
        marks.append("homoglyphs")
    if _BRACKET_AT.search(t) or _BRACKET_DOT.search(t):
        marks.append("bracket_obfuscation")
    if any(_printable(v) and len(v) >= 8 for v in decoded_variants(t)[:-1]):  # exclude rot13
        marks.append("encoded_payload")
    return marks
