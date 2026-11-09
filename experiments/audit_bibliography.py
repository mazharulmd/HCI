"""Create a title/year/source audit of 2023--2026 references via OpenAlex.

This checks bibliographic metadata only; it does not establish that a paper's
claims are supported by its full text. Four arXiv records that OpenAlex search
misranks are resolved directly through the arXiv Atom API.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "paper" / "references.bib"
OUT = ROOT / "docs" / "literature" / "openalex_metadata_audit.csv"
ARXIV_IDS = {
    "chen2025metasecalign": "2507.02735",
    "debenedetti2026camel": "2503.18813",
    "gong2025csagent": "2509.22256",
    "mozannar2025magentic": "2507.22358",
}
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def field(block: str, key: str) -> str:
    match = re.search(r"\b" + key + r"\s*=\s*\{", block, re.I)
    if not match:
        return ""
    pos, depth, chars = match.end(), 1, []
    while pos < len(block) and depth:
        char = block[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        chars.append(char)
        pos += 1
    return re.sub(r"\\[a-zA-Z]+\s*|[{}~]", " ", "".join(chars)).strip()


def normalized(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\s*|[{}~]", " ", text)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "CLEAR-bibliography-audit/1.0"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def arxiv_records(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    url = "https://export.arxiv.org/api/query?id_list=" + ",".join(ids)
    request = urllib.request.Request(url, headers={"User-Agent": "CLEAR-bibliography-audit/1.0"})
    root = ET.fromstring(urllib.request.urlopen(request, timeout=30).read())
    out = {}
    for entry in root.findall("a:entry", ATOM):
        ident = entry.findtext("a:id", namespaces=ATOM).rsplit("/", 1)[-1].split("v", 1)[0]
        title = " ".join((entry.findtext("a:title", namespaces=ATOM) or "").split())
        out[ident] = title
    return out


def main() -> None:
    raw = BIB.read_text(encoding="utf-8")
    refs = []
    pattern = re.compile(r"@\w+\s*\{([^,]+),([\s\S]*?)(?=\n@|\Z)")
    for match in pattern.finditer(raw):
        key, block = match.group(1), match.group(2)
        year_match = re.search(r"\byear\s*=\s*\{(\d{4})\}", block, re.I)
        if year_match and 2023 <= int(year_match.group(1)) <= 2026:
            refs.append({"key": key, "year": int(year_match.group(1)), "title": field(block, "title")})
    arxiv_titles = arxiv_records(list(ARXIV_IDS.values()))
    existing = {}
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as handle:
            existing = {row["key"]: row for row in csv.DictReader(handle)}
    rows = []
    for ref in refs:
        query = urllib.parse.quote(ref["title"])
        url = ("https://api.openalex.org/works?search=" + query +
               "&per-page=5&select=id,doi,title,publication_year,authorships,primary_location")
        row = existing.get(ref["key"], {"key": ref["key"], "bib_year": ref["year"], "bib_title": ref["title"],
               "openalex_title": "", "openalex_year": "", "venue": "", "doi": "",
               "authors": "", "similarity": "", "openalex_id": "", "verification": "unresolved",
               "secondary_record": ""})
        if row["verification"].startswith(("unresolved", "OpenAlex query error")):
            try:
                works = get_json(url).get("results", [])
                best = max(works, key=lambda work: difflib.SequenceMatcher(
                    None, normalized(ref["title"]), normalized(work["title"])).ratio(), default=None)
                if best:
                    ratio = difflib.SequenceMatcher(None, normalized(ref["title"]), normalized(best["title"])).ratio()
                    location = best.get("primary_location") or {}
                    source = location.get("source") or {}
                    authors = ", ".join(person["author"]["display_name"] for person in best.get("authorships", []))
                    row.update(openalex_title=best.get("title", ""), openalex_year=best.get("publication_year", ""),
                               venue=source.get("display_name", ""), doi=best.get("doi", ""), authors=authors,
                               similarity=f"{ratio:.3f}", openalex_id=best.get("id", ""),
                               verification="OpenAlex exact title" if ratio >= .95 else "OpenAlex near match" if ratio >= .82 else "manual check required")
            except Exception as exc:  # retain the record and report the failed lookup
                row["verification"] = "OpenAlex query error: " + type(exc).__name__
        arxiv_id = ARXIV_IDS.get(ref["key"])
        if arxiv_id and arxiv_id in arxiv_titles:
            row["secondary_record"] = "arXiv:" + arxiv_id + " — " + arxiv_titles[arxiv_id]
            if normalized(arxiv_titles[arxiv_id]) == normalized(ref["title"]):
                row["verification"] = "arXiv exact title; OpenAlex result also recorded"
        rows.append(row)
        print(ref["key"], row["verification"], flush=True)
        time.sleep(1.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} records to {OUT}")


if __name__ == "__main__":
    main()
