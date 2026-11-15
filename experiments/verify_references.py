"""Verify every entry of paper/references.bib against bibliographic databases.

    python experiments/verify_references.py

For each entry the title is matched in Semantic Scholar (title similarity >= 0.90),
which reports the venue, year, full author list, DOI and arXiv ID. If the record
has a DOI, the entry is rebuilt from Crossref's BibTeX for that DOI; otherwise it
is rebuilt from the Semantic Scholar record (published venue) or from arXiv
(preprints). Entries not found in Semantic Scholar are searched in Crossref and
arXiv directly. The citation key is kept, so the paper's citations do not change,
but author lists, venues, years and DOIs come from the databases, not from memory.
(DBLP serves a bot-check page to scripts, and OpenAlex requires an API key, so
neither is used.)

Writes
  docs/literature/reference_verification.csv   one row per entry: what was matched where
  paper/references_verified.bib                verified entries (unmatched ones kept and flagged)
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIB = ROOT / "paper" / "references.bib"
OUT_CSV = ROOT / "docs" / "literature" / "reference_verification.csv"
OUT_BIB = ROOT / "paper" / "references_verified.bib"
UA = {"User-Agent": "reference-verification-script/1.0"}
THRESH = 0.90


def get(url: str, retries: int = 4) -> bytes:
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except Exception as exc:  # rate limits and transient errors
            if k == retries - 1:
                raise
            time.sleep(3 * (k + 1) + (10 if "429" in str(exc) else 0))
    return b""


def norm(t: str) -> str:
    t = re.sub(r"[{}\\]", "", t).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def entries() -> list[tuple[str, str, str]]:
    text = BIB.read_text()
    out = []
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        out.append((m.group(1).lower(), m.group(2).strip(), m.group(0)))
    return out


def field(block: str, name: str) -> str:
    m = re.search(r"\b" + name + r"\s*=\s*\{", block, re.I)
    if not m:
        return ""
    i, depth = m.end(), 1
    j = i
    while j < len(block) and depth:
        depth += {"{": 1, "}": -1}.get(block[j], 0)
        j += 1
    return block[i:j - 1]


S2_FIELDS = "title,venue,year,authors,externalIds,publicationVenue,publicationTypes,journal"


def s2(title: str) -> dict | None:
    q = urllib.parse.quote(norm(title))
    for k in range(12):   # the public pool is heavily rate-limited
        try:
            data = json.loads(get(f"https://api.semanticscholar.org/graph/v1/paper/search/match?query={q}&fields={S2_FIELDS}", retries=1))
            break
        except Exception as exc:
            if "404" in str(exc):
                return None
            time.sleep(6 + 4 * k)
    else:
        raise RuntimeError("Semantic Scholar unavailable")
    for d in data.get("data", []):
        if sim(title, d.get("title", "")) >= THRESH:
            return d
    return None


def bib_from_s2(key: str, d: dict) -> str:
    authors = " and ".join(a["name"] for a in d.get("authors", []))
    ext = d.get("externalIds") or {}
    venue = (d.get("publicationVenue") or {}).get("name") or d.get("venue") or ""
    journal = (d.get("journal") or {})
    if venue and "arxiv" not in venue.lower():
        conf = "Conference" in (d.get("publicationTypes") or []) or not journal.get("volume")
        fields = [("author", authors), ("title", d["title"]), ("booktitle" if conf else "journal", venue),
                  ("year", str(d.get("year", "")))]
        if not conf and journal.get("volume"):
            fields.append(("volume", journal["volume"]))
        if journal.get("pages"):
            fields.append(("pages", journal["pages"].replace(" ", "")))
        typ = "inproceedings" if conf else "article"
    else:
        fields = [("author", authors), ("title", d["title"]), ("year", str(d.get("year", ""))),
                  ("howpublished", "arXiv:" + ext.get("ArXiv", "")), ("note", "Preprint")]
        typ = "misc"
    if ext.get("DOI"):
        fields.append(("doi", ext["DOI"]))
    return "@" + typ + "{" + key + ",\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v) + "\n}"


def dblp(title: str) -> list[dict]:
    q = urllib.parse.quote(norm(title))
    data = json.loads(get(f"https://dblp.org/search/publ/api?q={q}&format=json&h=10"))
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    out = []
    for h in hits:
        info = h["info"]
        s = sim(title, info.get("title", ""))
        if s >= THRESH:
            out.append({"key": info["key"], "title": info.get("title", ""), "venue": info.get("venue", ""),
                        "year": info.get("year", ""), "type": info.get("type", ""), "doi": info.get("doi", ""),
                        "sim": round(s, 3)})
    return out


def dblp_bib(key: str) -> str:
    return get(f"https://dblp.org/rec/{key}.bib").decode()


def crossref(title: str) -> dict | None:
    q = urllib.parse.quote(title)
    data = json.loads(get(f"https://api.crossref.org/works?query.bibliographic={q}&rows=5"))
    for it in data["message"]["items"]:
        t = (it.get("title") or [""])[0]
        if sim(title, t) >= THRESH:
            return {"doi": it["DOI"], "title": t, "venue": (it.get("container-title") or [""])[0],
                    "year": str((it.get("issued", {}).get("date-parts") or [[""]])[0][0]), "sim": round(sim(title, t), 3)}
    return None


def crossref_bib(doi: str) -> str:
    return get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}/transform/application/x-bibtex").decode()


def arxiv(title: str) -> dict | None:
    q = urllib.parse.quote('ti:"' + norm(title) + '"')
    xml = get(f"https://export.arxiv.org/api/query?search_query={q}&max_results=5")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(xml).findall("a:entry", ns):
        t = " ".join(e.find("a:title", ns).text.split())
        if sim(title, t) >= THRESH:
            aid = e.find("a:id", ns).text.rsplit("/", 1)[-1]
            authors = [a.find("a:name", ns).text for a in e.findall("a:author", ns)]
            return {"id": re.sub(r"v\d+$", "", aid), "title": t, "authors": authors,
                    "year": e.find("a:published", ns).text[:4], "sim": round(sim(title, t), 3)}
    return None


def rekey(bib: str, key: str) -> str:
    bib = re.sub(r"^(@\w+\{)[^,]+,", lambda m: m.group(1) + key + ",", bib.strip(), count=1)
    bib = re.sub(r"\n\s*(timestamp|biburl|bibsource|url)\s*=\s*\{[^\n]*\},?", "", bib)   # DBLP housekeeping
    return bib


def main() -> None:
    rows, out_bib = [], []
    for typ, key, block in entries():
        title = field(block, "title")
        row = {"key": key, "bib_title": re.sub(r"[{}]", "", title), "bib_year": field(block, "year"),
               "source": "", "matched_title": "", "venue": "", "year": "", "record": "", "similarity": "",
               "peer_reviewed": "", "note": ""}
        new = None
        try:
            d = s2(title)
            if d:
                ext = d.get("externalIds") or {}
                venue = (d.get("publicationVenue") or {}).get("name") or d.get("venue") or ""
                published = bool(venue) and "arxiv" not in venue.lower()
                row.update(source="SemanticScholar", matched_title=d["title"], venue=venue, year=str(d.get("year", "")),
                           record=ext.get("DOI") or ("arXiv:" + ext["ArXiv"] if ext.get("ArXiv") else d.get("paperId", "")),
                           similarity=round(sim(title, d["title"]), 3), peer_reviewed=str(published))
                new = None
                if ext.get("DOI") and not ext["DOI"].lower().startswith("10.48550"):
                    try:
                        new = rekey(crossref_bib(ext["DOI"]), key)
                        row["note"] = "BibTeX from Crossref"
                    except Exception:
                        new = None
                if new is None:
                    new = bib_from_s2(key, d)
                    row["note"] = row["note"] or "BibTeX from Semantic Scholar record"
            else:
                cr = crossref(title)
                if cr:
                    row.update(source="Crossref", matched_title=cr["title"], venue=cr["venue"], year=cr["year"],
                               record=cr["doi"], similarity=cr["sim"], peer_reviewed="True")
                    new = rekey(crossref_bib(cr["doi"]), key)
                else:
                    ax = arxiv(title)
                    time.sleep(3)
                    if ax:
                        row.update(source="arXiv", matched_title=ax["title"], venue="arXiv", year=ax["year"],
                                   record=ax["id"], similarity=ax["sim"], peer_reviewed="False")
                        new = ("@misc{" + key + ",\n  author = {" + " and ".join(ax["authors"]) + "},\n  title = {"
                               + ax["title"] + "},\n  year = {" + ax["year"] + "},\n  howpublished = {arXiv:" + ax["id"]
                               + "},\n  note = {Preprint}\n}")
                    else:
                        row.update(source="NOT FOUND", note="kept unchanged; check by hand")
            time.sleep(1.5)
        except Exception as exc:
            row.update(source="ERROR", note=f"{exc.__class__.__name__}: {exc}"[:200])
        out_bib.append(new if new else block)
        rows.append(row)
        print(f"{row['source']:9} {key:28} {row['similarity']!s:5} {row['venue'][:40]} {row['year']}")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    OUT_BIB.write_text("\n\n".join(out_bib) + "\n")
    print("wrote", OUT_CSV, OUT_BIB)


if __name__ == "__main__":
    main()
