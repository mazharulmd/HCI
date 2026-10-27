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


_ESCAPES = re.compile(r"\\[ntr]")
_B64_RUN = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")


def _try_b64(blob: str, min_len: int = 8) -> str | None:
    try:
        dec = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=False).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    return dec if _printable(dec) and len(dec) >= min_len else None


def _try_hex(blob: str, min_len: int = 8) -> str | None:
    try:
        dec = bytes.fromhex(blob[: len(blob) // 2 * 2]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return dec if _printable(dec) and len(dec) >= min_len else None


def decoded_variants(text: str, robust: bool = False) -> list[str]:
    """Texts hidden inside ``text`` by common encodings (each returned once).

    ``robust`` (v2.1): un-escape literal ``\\n``/``\\t`` sequences of serialised tool
    output and tolerate payloads glued to preceding characters by trying the
    first few start offsets of every candidate run. v2 used word-boundary
    matching only, which missed payloads glued to an escaped newline.
    """
    out: list[str] = []
    t = text or ""
    if not robust:   # exactly the frozen v2 behaviour
        for m in _B64.finditer(t):
            dec = _try_b64(m.group(0), 0)
            if dec:
                out.append(dec)
        for m in _HEX.finditer(t):
            dec = _try_hex(m.group(0), 0)
            if dec:
                out.append(dec)
    else:
        t = _ESCAPES.sub(" ", t)
        for m in _B64_RUN.finditer(t):
            run = m.group(0)
            for off in range(0, min(8, len(run) - 15)):
                dec = _try_b64(run[off:])
                if dec:
                    out.append(dec)
                    break
        for m in _HEX_RUN.finditer(t):
            run = m.group(0)
            for off in (0, 1):
                dec = _try_hex(run[off:])
                if dec:
                    out.append(dec)
                    break
    text = text or ""
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


def obfuscation_markers(text: str, robust: bool = False) -> list[str]:
    """Which hiding techniques are present in ``text``."""
    t = text or ""
    marks = []
    if _INVISIBLE.search(t):
        marks.append("invisible_characters")
    if t != t.translate(_CONFUSABLES) and re.search(r"[A-Za-z]", t):
        marks.append("homoglyphs")
    if _BRACKET_AT.search(t) or _BRACKET_DOT.search(t):
        marks.append("bracket_obfuscation")
    rot = codecs.decode(t, "rot13")
    if any(v != rot and _printable(v) and len(v) >= 8 for v in decoded_variants(t, robust)):
        marks.append("encoded_payload")
    return marks
