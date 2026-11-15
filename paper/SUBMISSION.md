# Submission package: *Information Processing & Management* (Elsevier)

The review is **double-anonymized**: the manuscript contains no author names,
affiliations or identifying links; author details are only on the title page.

## Building the package

```bash
scripts/build_paper.sh                                   # paper/main.pdf (anonymized manuscript)
python scripts/latex_to_docx.py --out paper/submission_ipm/Manuscript_anonymized.docx
```

The upload files (manuscript PDF/DOCX/LaTeX zip, highlights, title page, cover
letter) are kept in `paper/submission_ipm/`, which is **not** tracked by git,
because the title page and cover letter contain the authors' personal details.

## Upload checklist (required files on the submission form)

| Upload type | File |
|---|---|
| Cover letter (with the point-by-point response to the editor) | `Cover_letter_with_response.docx` (or `.pdf`) |
| Manuscript without author details | `Manuscript_anonymized.docx` or `Manuscript_anonymized.pdf`; LaTeX source in `Manuscript_LaTeX_source.zip` |
| Highlights | `Highlights.docx` (editable file, 5 bullets of at most 85 characters) |
| Title page with author details | `Title_page.docx` (or `.pdf`; LaTeX: `Title_page.tex`) |
| Supplementary material | `Supplementary_reference_verification.csv` (how every reference was verified) |

## Journal requirements checked

* Abstract of at most 250 words (248).
* 1–7 keywords (7).
* Highlights: 5 bullets of 22–27 words, as the senior editor asked (15–30 words each).
* References in APA style (apacite); every entry verified (see the supplementary table).
* Generative-AI declaration placed directly before the references.
* Data availability statement with the repository link withheld for review.
* No author-identifying text or document metadata in the manuscript files.

Elsevier's own pages could not be opened from the preparation environment; the
abstract and keyword limits were taken from search results quoting the
journal's Guide for Authors. Re-check the Guide for Authors when submitting.

## Before submitting, the authors must confirm

1. Acknowledgements ("None"), funding ("no specific grant") and the competing-interest
   statement on the title page.
2. The cover letter's statements that all authors approve the submission and that
   the manuscript is not under consideration elsewhere.
3. The generative-AI declaration: it states that the authors reviewed and edited
   the content and take full responsibility for it, so every author should read
   the manuscript.
4. The CRediT author contribution statement is not part of the package because
   each author's roles must come from the authors; the journal requests it at
   revision or acceptance.
5. Optional: 26 bibliography entries still end in "et al." and 18 arXiv entries lack
   an arXiv identifier (see `references.bib`).
6. On acceptance, restore the repository link in the data availability statement.

## What the paper does not claim

* No human participants were studied. The user study is a proposed protocol with
  an apparatus and a power analysis; every result about people is from a labelled
  simulation.
* No new live LLM runs were made; the evaluation replays recorded AgentDojo
  trajectories.
