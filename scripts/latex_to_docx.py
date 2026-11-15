"""Convert the LaTeX manuscript (paper/main.tex) to a Word file for submission systems.

    python scripts/latex_to_docx.py --out paper/submission_ipm/Manuscript_anonymized.docx

Run scripts/build_paper.sh first: cross-reference numbers are taken from the
LaTeX build (paper/main.aux), so the Word file shows the same section, table,
figure and proposition numbers as the PDF. The script
  * inlines \\input{generated/...} tables and drops \\resizebox wrappers,
  * replaces \\cref/\\Cref/\\ref with the numbers LaTeX assigned,
  * renders the TikZ architecture figure to PNG and uses PNG versions of figures,
  * turns the elsarticle front matter into plain title, abstract and keywords,
  * formats citations with pandoc citeproc and the APA CSL style (as IP&M).
The PDF built by LaTeX remains the reference version of the manuscript.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
CSL_URL = "https://raw.githubusercontent.com/citation-style-language/styles/master/apa.csl"
KIND = {"section": "Section", "subsection": "Section", "subsubsection": "Section", "table": "Table",
        "figure": "Figure", "proposition": "Proposition", "definition": "Definition", "equation": "Eq.",
        "appendix": "Appendix", "remark": "Remark", "enumi": "item"}


def braced(s: str, i: int) -> int:
    """Index just after the brace group that opens at s[i] == '{'."""
    depth = 0
    for j in range(i, len(s)):
        depth += {"{": 1, "}": -1}.get(s[j], 0)
        if depth == 0:
            return j + 1
    raise ValueError("unbalanced braces")


def inline_inputs(tex: str) -> str:
    def sub(m):
        f = PAPER / (m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex")
        return inline_inputs(f.read_text())
    return re.sub(r"\\input\{([^}]+)\}", sub, tex)


def drop_wrapper(tex: str, cmd: str, nargs_before: int) -> str:
    """Replace \\cmd{a}{b}{BODY} (nargs_before arguments before BODY) by BODY."""
    out, i = [], 0
    while True:
        k = tex.find(cmd, i)
        if k < 0:
            return "".join(out) + tex[i:]
        j = k + len(cmd)
        for _ in range(nargs_before):
            j = braced(tex, j)
        end = braced(tex, j)
        out.append(tex[i:k] + tex[j + 1:end - 1])
        i = end


def label_map() -> dict[str, tuple[str, str]]:
    aux = (PAPER / "main.aux").read_text()
    kinds = dict(re.findall(r"\\newlabel\{([^}@]+)@cref\}\{\{\[([a-z]+)\]", aux))
    nums = dict(re.findall(r"\\newlabel\{([^}@]+)\}\{\{([^}]*)\}", aux))
    return {k: (KIND.get(kinds.get(k, ""), ""), n) for k, n in nums.items()}


def resolve_refs(tex: str, labels: dict) -> str:
    def cref(m):
        cap, keys = m.group(1) == "C", [k.strip() for k in m.group(2).split(",")]
        parts, prev = [], None
        for k in keys:
            kind, num = labels.get(k, ("", "??"))
            num = num.replace("~", " ")
            if num.startswith("Appendix"):   # elsarticle numbers appendices "Appendix C"
                kind, num = "Appendix", num.split()[-1]
            parts.append(num if kind == prev else f"{kind} {num}".strip())
            prev = kind
        text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
        return text[0].upper() + text[1:] if cap else text
    tex = re.sub(r"\\(c|C)ref\{([^}]+)\}", cref, tex)
    tex = re.sub(r"\\eqref\{([^}]+)\}", lambda m: f"({labels.get(m.group(1), ('', '??'))[1]})", tex)
    return re.sub(r"\\ref\{([^}]+)\}", lambda m: labels.get(m.group(1), ("", "??"))[1], tex)


def render_tikz(tex: str, workdir: Path) -> str:
    m = re.search(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", tex, re.S)
    if not m:
        return tex
    pre = (PAPER / "main.tex").read_text()
    lib = "\n".join(re.findall(r"\\usetikzlibrary\{[^}]+\}", pre))
    doc = ("\\documentclass[border=4pt]{standalone}\n\\usepackage[T1]{fontenc}\\usepackage{lmodern}"
           "\\usepackage{amsmath,amssymb}\\usepackage{tikz}\n" + lib +
           "\n\\newcommand{\\clear}{\\textsc{Clear}}\\newcommand{\\tier}[1]{\\textsf{#1}}\n"
           "\\begin{document}\n" + m.group(0) + "\n\\end{document}\n")
    (workdir / "arch.tex").write_text(doc)
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "arch.tex"], cwd=workdir, check=True,
                   capture_output=True)
    subprocess.run(["pdftoppm", "-r", "220", "-png", "-singlefile", "arch.pdf", "arch"], cwd=workdir, check=True)
    return tex[:m.start()] + "\\includegraphics[width=\\linewidth]{" + str(workdir / "arch.png") + "}" + tex[m.end():]


def number_captions(tex: str, labels: dict) -> str:
    """Prefix each figure/table caption with the number LaTeX gave it (pandoc does not number them)."""
    def env(m):
        body = m.group(0)
        lab = re.search(r"\\label\{([^}]+)\}", body)
        if not lab or "\\caption{" not in body:
            return body
        kind, num = labels.get(lab.group(1), ("", "?"))
        kind = kind or ("Table" if m.group(1) == "table" else "Figure")
        if "\\begin{subfigure}" in body:   # panels become (a), (b); the number goes on the main caption
            panels = iter("abcdefgh")
            parts = re.split(r"(\\end\{subfigure\})", body)
            parts = [x.replace("\\caption{", "\\caption{(" + next(panels) + ") ", 1) if "\\begin{subfigure}" in x else x
                     for x in parts]
            body = "".join(parts)
            k = body.rfind("\\caption{")
            return body[:k] + "\\caption{" + f"{kind} {num}. " + body[k + len("\\caption{"):]
        return body.replace("\\caption{", "\\caption{" + f"{kind} {num}. ", 1)
    return re.sub(r"\\begin\{(figure|table)\*?\}.*?\\end\{\1\*?\}", env, tex, flags=re.S)


def structure(tex: str) -> str:
    """Run-in paragraph headings as in the PDF, and lettered appendices (sections get pandoc numbers)."""
    tex = re.sub(r"\\paragraph\{([^}]*)\}", r"\\textbf{\1} ", tex)
    if "\\appendix" in tex:
        head, tail = tex.split("\\appendix", 1)
        letters = iter("ABCDEFGH")
        tail = re.sub(r"\\section\{([^}]*)\}", lambda m: "\\section*{Appendix " + next(letters) + ". " + m.group(1) + "}", tail)
        tex = head + tail
    return tex


def frontmatter(tex: str) -> str:
    kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", tex, re.S)
    words = "; ".join(w.strip() for w in kw.group(1).replace("\n", " ").split("\\sep")) if kw else ""
    tex = re.sub(r"\\begin\{keyword\}.*?\\end\{keyword\}",
                 lambda _: "\n\\noindent\\textbf{Keywords:} " + words + "\n", tex, flags=re.S)
    for pat in (r"\\begin\{frontmatter\}", r"\\end\{frontmatter\}", r"\\linenumbers[^\n]*", r"\\journal\{[^}]*\}"):
        tex = re.sub(pat, "", tex)
    return tex


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PAPER / "main.docx"))
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        tex = (PAPER / "main.tex").read_text()
        tex = inline_inputs(tex)
        tex = drop_wrapper(tex, "\\resizebox", 2)
        labels = label_map()
        tex = number_captions(tex, labels)
        tex = resolve_refs(tex, labels)
        tex = structure(tex)
        tex = render_tikz(tex, work)
        tex = frontmatter(tex)
        tex = re.sub(r"\{figures/([\w-]+)\.pdf\}", lambda m: "{" + str(ROOT / "figures" / (m.group(1) + ".png")) + "}", tex)
        tex = re.sub(r"\{figures/([\w-]+\.png)\}", lambda m: "{" + str(ROOT / "figures" / m.group(1)) + "}", tex)
        (work / "flat.tex").write_text(tex)
        csl = work / "apa.csl"
        urllib.request.urlretrieve(CSL_URL, csl)
        shutil.copy(PAPER / "references.bib", work / "references.bib")
        subprocess.run(["pandoc", "flat.tex", "-f", "latex", "-t", "docx", "--citeproc",
                        "--bibliography", "references.bib", "--csl", str(csl),
                        "-M", "reference-section-title=References", "--number-sections", "-o", str(out)],
                       cwd=work, check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
