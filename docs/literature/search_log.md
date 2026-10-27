# Supplemental search log — 27 October 2026

This supplements the earlier structured rapid review. It is not a full
systematic-review export: OpenAlex `search` returns ranked works, and we
requested only 50 records for each query. One reviewer screened this sample.
The scope is 2023-01-01 through 2026-10-27.

For each row, the request used
`https://api.openalex.org/works?search={URL-encoded query}&filter=from_publication_date:2023-01-01,to_publication_date:2026-10-27&per-page=50&select=id,doi,title,publication_year,type,authorships,primary_location,open_access,abstract_inverted_index`.
The returned API `meta.count` is the total matching count; it is not the number
screened. 400 ranked records were retrieved across the eight searches and
deduplicated to 342 OpenAlex work IDs. See `systematic_review.md` for scope,
screening limits, and the revised novelty analysis. Bibliographic title
metadata is separately checked in `openalex_metadata_audit.csv`.

| Search key | Exact query | API total | Returned | Retrieval date |
|---|---|---:|---:|---|
| agent_prompt_injection | indirect prompt injection AI agents tool use defense | 4,349 | 50 | 2026-10-27 |
| agentdojo_defense | AgentDojo prompt injection defense agent benchmark | 1,295 | 50 | 2026-10-27 |
| agent_security_benchmark | agent security benchmark prompt injection attacks defenses | 5,817 | 50 | 2026-10-27 |
| human_agent_permissions | user permission decisions AI agents human computer interaction | 15,539 | 50 | 2026-10-27 |
| human_prompt_injection_ui | prompt injection interface user study human oversight agent | 2,765 | 50 | 2026-10-27 |
| confirmation_risk_cards | prompt injection risk card confirmation UI agent | 155 | 50 | 2026-10-27 |
| provenance_tool_authorization | provenance tool authorization LLM agents human oversight | 791 | 50 | 2026-10-27 |
| tool_call_security_warnings | AI agent tool calls security warning usability | 16,810 | 50 | 2026-10-27 |

## Targeted source checks

- OpenAlex and Crossref DOI record for Su, Rao, and Ma's Risk Cards article:
  DOI `10.51903/ijgd.v4i1.3699`. OpenAlex returned its abstract. The publisher
  PDF request to `journal.stekom.ac.id` returned HTTP 403; full-text claims
  were not independently checked.
- arXiv Atom API exact-title checks: Meta-SecAlign (`2507.02735`), CaMeL
  (`2503.18813`), computer-use agent access control (`2509.22256`), and
  Magentic-UI (`2507.22358`). These resolve four low-similarity OpenAlex
  search results; see the metadata audit.
- Crossref DOI checks for Greshake et al. (AISec 2023), Risk Cards (2026), and
  Zhang and Wang (CHI EA 2026). DOI and venue metadata are included in the
  BibTeX records.

OpenAlex titles and primary-source metadata identify records; they do not
verify the underlying claims. Publication status is distinguished from
preprint status in the bibliography where confirmed. The complete screening
decisions for all 342 ranked works are not yet independently double-coded;
therefore the review is described as a rapid review rather than PRISMA-complete.

The current reference audit has 52 recent bibliography entries: 22 exact-title
OpenAlex matches and four exact-title arXiv checks. The remaining 26 OpenAlex
lookups ended in remote disconnects after retries and are marked unresolved in
the CSV; they are not represented as verified by this audit. Key records used
to define the novelty boundary (Risk Cards, CaMeL, Meta-SecAlign, CSAgent,
Magentic-UI, and the 2026 permission studies) also received targeted DOI or
arXiv checks recorded above.
