"""Assemble the final, verified bibliography from the verification run.

    python experiments/verify_references.py     # matches every entry (writes the CSV and raw BibTeX)
    python experiments/build_bibliography.py    # writes paper/references.bib

Rules (see docs/literature/reference_verification.csv for the per-entry evidence):
  * entry with a publisher DOI: the publisher's own record from Crossref;
  * peer-reviewed paper without a DOI (USENIX, NeurIPS, ICLR, ICML, ...): author names as
    written on the paper (arXiv record), venue of the published version, year of publication;
  * preprint with no peer-reviewed version found: arXiv record (authors, year, identifier);
  * a few entries are fixed by hand below (OVERRIDES), each with its source.
Titles get braces around acronyms and proper nouns so that the APA style keeps their case.
"""
from __future__ import annotations

import csv
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "docs" / "literature" / "reference_verification.csv"
RAW = ROOT / "paper" / "references_verified.bib"
OLD = ROOT / "paper" / "references.bib"
OUT = ROOT / "paper" / "references.bib"
UA = {"User-Agent": "bibliography-builder/1.0"}

# Published venues of peer-reviewed papers without a publisher DOI in the verification run:
# key -> (entry type, venue field, venue, year). Venue and year as published; checked against the
# verified match (Semantic Scholar venue) in reference_verification.csv.
PUBLISHED = {
    "liu2024formalizing": ("inproceedings", "booktitle", "33rd USENIX Security Symposium (USENIX Security 24)", "2024"),
    "zhan2024injecagent": ("inproceedings", "booktitle", "Findings of the Association for Computational Linguistics: ACL 2024", "2024"),
    "debenedetti2024agentdojo": ("inproceedings", "booktitle", "Advances in Neural Information Processing Systems 37 (NeurIPS 2024), Datasets and Benchmarks Track", "2024"),
    "zhang2025asb": ("inproceedings", "booktitle", "The Thirteenth International Conference on Learning Representations (ICLR 2025)", "2025"),
    "zhan2025adaptive": ("inproceedings", "booktitle", "Findings of the Association for Computational Linguistics: NAACL 2025", "2025"),
    "hines2024spotlighting": ("inproceedings", "booktitle", "Conference on Applied Machine Learning in Information Security (CAMLIS 2024)", "2024"),
    "chen2025struq": ("inproceedings", "booktitle", "34th USENIX Security Symposium (USENIX Security 25)", "2025"),
    "zhu2025melon": ("inproceedings", "booktitle", "Proceedings of the 42nd International Conference on Machine Learning (ICML 2025)", "2025"),
    "jia2025taskshield": ("inproceedings", "booktitle", "Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (ACL 2025)", "2025"),
    "an2025ipiguard": ("inproceedings", "booktitle", "Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing (EMNLP 2025)", "2025"),
    "li2025drift": ("inproceedings", "booktitle", "Advances in Neural Information Processing Systems 38 (NeurIPS 2025)", "2025"),
    "cranor2008framework": ("inproceedings", "booktitle", "Usability, Psychology, and Security (UPSEC 2008)", "2008"),
    "sunshine2009crying": ("inproceedings", "booktitle", "18th USENIX Security Symposium", "2009"),
    "akhawe2013alice": ("inproceedings", "booktitle", "22nd USENIX Security Symposium", "2013"),
}
# Entries kept or set by hand (bibliographic facts from the cited works themselves).
OVERRIDES = {
    "perez2022ignore": "@inproceedings{perez2022ignore,\n  title = {Ignore Previous Prompt: Attack Techniques for Language Models},\n  author = {Perez, F{\\'a}bio and Ribeiro, Ian},\n  booktitle = {NeurIPS ML Safety Workshop},\n  year = {2022},\n  note = {arXiv:2211.09527}\n}",
    "nissenbaum2004privacy": "@article{nissenbaum2004privacy,\n  title = {Privacy as Contextual Integrity},\n  author = {Nissenbaum, Helen},\n  journal = {Washington Law Review},\n  volume = {79},\n  number = {1},\n  pages = {119--157},\n  year = {2004}\n}",
    # current (3rd) edition; Crossref DOI 10.4324/9781003203636
    "macmillan2005detection": "@book{macmillan2005detection,\n  title = {Detection Theory: A User's Guide},\n  author = {Hautus, Michael J. and Macmillan, Neil A. and Creelman, C. Douglas},\n  edition = {3rd},\n  publisher = {Routledge},\n  year = {2021},\n  doi = {10.4324/9781003203636}\n}",
}
EXTRA_DOI = {"bucinca2021trust": "10.1145/3449287"}   # published version of an entry matched only on arXiv
PROPER = {"Android", "Alice", "Warningland", "Humans", "Automation", "NASA", "Web", "Copilot", "Washington"}


def get(url: str) -> bytes:
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except Exception:
            if k == 3:
                raise
            time.sleep(4 * (k + 1))
    return b""


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", re.sub(r"[{}\\]", "", t).lower())).strip()


def arxiv(title: str) -> dict | None:
    import difflib
    q = urllib.parse.quote('ti:"' + norm(title) + '"')
    xml = get(f"https://export.arxiv.org/api/query?search_query={q}&max_results=5")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(xml).findall("a:entry", ns):
        t = " ".join(e.find("a:title", ns).text.split())
        if difflib.SequenceMatcher(None, norm(title), norm(t)).ratio() >= 0.9:
            return {"id": re.sub(r"v\d+$", "", e.find("a:id", ns).text.rsplit("/", 1)[-1]), "title": t,
                    "authors": [a.find("a:name", ns).text for a in e.findall("a:author", ns)],
                    "year": e.find("a:published", ns).text[:4]}
    return None


def protect(title: str) -> str:
    """Brace acronyms, CamelCase names, listed proper nouns and the first word after a colon or
    question mark, so that the APA style's sentence case keeps them (APA 7)."""
    title = re.sub(r"[{}]", "", title)

    def part(p):
        core = re.sub(r"[^\w]", "", p)
        if core and (sum(c.isupper() for c in core[1:]) > 0 or core in PROPER
                     or (any(c.isdigit() for c in core) and any(c.isupper() for c in core))):
            return p.replace(core, "{" + core + "}", 1)
        return p

    words, out, cap_next = title.split(), [], False
    for w in words:
        w2 = "-".join(part(x) for x in w.split("-"))
        if cap_next and w2[:1].isalpha():   # APA: capitalise the first word after a colon or question mark
            w2 = "{" + w2[0].upper() + "}" + w2[1:]
        out.append(w2)
        cap_next = w.endswith(":") or w.endswith("?")
    return " ".join(out)


def field_value(entry: str, name: str) -> tuple[int, int] | None:
    """Span of the braced value of a field (handles nested braces)."""
    m = re.search(r"\b" + name + r"\s*=\s*\{", entry, re.I)
    if not m:
        return None
    i, depth, j = m.end(), 1, m.end()
    while j < len(entry) and depth:
        depth += {"{": 1, "}": -1}.get(entry[j], 0)
        j += 1
    return i, j - 1


def polish(entry: str) -> str:
    entry = re.sub(r",?\s*month\s*=\s*\{?[A-Za-z]+\}?(?=\s*[,}])", "", entry)
    span = field_value(entry, "title")
    if span:
        entry = entry[:span[0]] + protect(entry[span[0]:span[1]]) + entry[span[1]:]
    for name in ("booktitle", "journal"):   # APA keeps venue names in title case
        span = field_value(entry, name)
        if span and not entry[span[0]:span[1]].startswith("{"):
            entry = entry[:span[0]] + "{" + entry[span[0]:span[1]] + "}" + entry[span[1]:]
    ax = re.search(r"howpublished\s*=\s*\{arXiv:([\d.]+)\}", entry)
    if ax:   # APA 7 preprint: archive name and DOI
        entry = entry.replace(ax.group(0), "howpublished = {arXiv preprint arXiv:" + ax.group(1) + "}")
        entry = re.sub(r",\s*note\s*=\s*\{Preprint\}", ",\n  doi = {10.48550/arXiv." + ax.group(1) + "}", entry)
    if entry.startswith("@inproceedings") or entry.startswith("@article") or entry.startswith("@incollection"):
        entry = re.sub(r",\s*note\s*=\s*\{arXiv:[^}]*\}", "", entry)   # published version: no arXiv note
    return entry


def entries(path: Path) -> dict[str, str]:
    text = path.read_text()
    out = {}
    for m in re.finditer(r"@\w+\{([^,]+),.*?(?=\n@|\Z)", text, re.S):
        out[m.group(1).strip()] = m.group(0).strip()
    return out


def fmt(typ: str, key: str, fields: list[tuple[str, str]]) -> str:
    return "@" + typ + "{" + key + ",\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in fields if v) + "\n}"


def crossref_bib(doi: str, key: str) -> str:
    bib = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}/transform/application/x-bibtex").decode()
    return re.sub(r"^(@\w+\{)[^,]+,", lambda m: m.group(1) + key + ",", bib.strip(), count=1)


def tidy_crossref(bib: str) -> str:
    bib = re.sub(r",?\s*url=\{[^}]*\}", "", bib)
    bib = re.sub(r"title=\{(.*?)\}, (?=[a-zA-Z]+=)", lambda m: "title={" + protect(m.group(1)) + "}, ", bib, count=1)
    return bib.replace("pages={", "pages={").replace("–", "--")


def main() -> None:
    rows = list(csv.DictReader(open(CSV)))
    raw, old = entries(RAW), entries(OLD)
    out, log = [], []
    for r in rows:
        k = r["key"]
        if k in OVERRIDES:
            out.append(OVERRIDES[k]); log.append((k, "manual"))
            continue
        if k in EXTRA_DOI:
            out.append(tidy_crossref(crossref_bib(EXTRA_DOI[k], k))); log.append((k, "Crossref " + EXTRA_DOI[k]))
            continue
        if r["note"] == "BibTeX from Crossref" or r["source"] == "Crossref":
            out.append(tidy_crossref(raw[k])); log.append((k, "Crossref " + r["record"]))
            continue
        ax = arxiv(r["matched_title"] or r["bib_title"])
        time.sleep(3)
        if k in PUBLISHED:
            typ, vf, venue, year = PUBLISHED[k]
            authors = " and ".join(ax["authors"]) if ax else re.search(r"author = \{(.*?)\}", raw[k]).group(1)
            fields = [("title", protect(ax["title"] if ax else r["matched_title"])), ("author", authors), (vf, venue), ("year", year)]
            if ax:
                fields.append(("note", "arXiv:" + ax["id"]))
            out.append(fmt(typ, k, fields)); log.append((k, f"published, authors from {'arXiv' if ax else 'S2'}"))
        elif ax:
            fields = [("title", protect(ax["title"])), ("author", " and ".join(ax["authors"])), ("year", ax["year"]),
                      ("howpublished", "arXiv:" + ax["id"]), ("note", "Preprint")]
            out.append(fmt("misc", k, fields)); log.append((k, "arXiv " + ax["id"]))
        else:
            out.append(old[k]); log.append((k, "UNCHANGED (no arXiv record)"))
    OUT.write_text("\n\n".join(polish(e) for e in out) + "\n")
    for k, how in log:
        print(f"{k:30} {how}")


if __name__ == "__main__":
    import sys
    if "--polish-only" in sys.argv:   # re-apply formatting to the current file without network access
        OUT.write_text("\n\n".join(polish(e) for e in entries(OUT).values()) + "\n")
    else:
        main()
