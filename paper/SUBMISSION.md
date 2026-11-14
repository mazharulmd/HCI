# Submission package: *Computers & Security* (Elsevier)

## Why this journal

*Computers & Security* is the Elsevier journal linked to IFIP TC11 (security and
privacy protection), which includes a working group on the human aspects of
security. The paper is a security paper with a human-factors design contribution:
a defence against prompt injection in AI agents, evaluated on real agent
trajectories, plus a proposed user study. A human-subject study is not a
requirement for this journal, whereas HCI journals such as IJHCS or TOCHI would
expect one. Check the journal's current quartile and impact factor yourself in
Scopus/SCImago or JCR before submitting.

## Files to upload

| File | Purpose |
|---|---|
| `main.pdf` | manuscript (compiled) |
| `main.tex`, `references.bib`, `generated/`, `figures/` | LaTeX source (elsarticle class, author-year references) |
| `highlights.txt` | highlights, 5 bullets of at most 85 characters (required as a separate file) |
| `cover_letter.md` | cover letter (paste into the submission system) |

Build from the repository root with `scripts/build_paper.sh`.

## Requirements checked

* Abstract of at most 250 words (248).
* 3–5 highlights of at most 85 characters each (5).
* 5–10 keywords (8).
* Declarations: CRediT author contributions, competing interest, funding, data
  availability, ethics, and the Elsevier statement on generative AI use.
* Line numbers for reviewers.

Elsevier's own pages could not be opened from the environment where this was
prepared. These requirements were taken from search results quoting the
journal's Guide for Authors. Re-check them on the Guide for Authors page when
you submit.

## Things only the author can do before submitting

1. **Author block.** Replace `[Author name]`, `[Department, University]`, `[City]`,
   `[Country]` and `[corresponding e-mail]` in `main.tex` (front matter and CRediT
   statement) and in `cover_letter.md`. Add co-authors if there are any.
2. **Confirm the declarations** in `main.tex`: no competing interests, no specific
   funding. Change them if they are not true.
3. **Read the whole manuscript.** The generative-AI declaration states that the
   authors reviewed and edited the content and take full responsibility for it.
   That statement must be true when you submit.
4. **Complete 26 reference entries** that still end in "et al." (their full author
   lists could not be retrieved from the preparation environment). On a computer
   with internet access, `python experiments/audit_bibliography.py` writes the
   author lists it finds to `docs/literature/openalex_metadata_audit.csv`; copy
   them into the entries with `and others` in `references.bib`, or complete
   those entries from Google Scholar.
5. Add an arXiv identifier to the 18 entries whose note only says "arXiv preprint".

## What the paper does not claim

* No human participants were studied. The user study is a proposed protocol
  with an apparatus and a power analysis; every result about people is from a
  labelled simulation.
* No new live LLM runs were made; the evaluation replays recorded AgentDojo
  trajectories.
