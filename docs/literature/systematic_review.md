# Structured literature review (2023 – Oct 2026)

**Type.** A structured *rapid* review with a documented search, explicit inclusion
criteria and a taxonomy. We do **not** claim a full PRISMA systematic review,
because screening was done by a single reviewer (the research agent) and the
search was limited to two discovery services. All queries are listed below so
the search can be re-run and extended.

## Search protocol

* **Initial search:** 26 October 2026; **supplemental OpenAlex search:** 27 October 2026 (documented below).
* **Discovery services.**
  1. Consensus (semantic search over Semantic Scholar / OpenAlex / PubMed records). Each query returns the top 10 records with title, authors, year and venue.
  2. A general web search engine, used for publisher pages (ACM DL, USENIX, IEEE), arXiv listings and DBLP-like pages.
* **Initial retrieval limitation.** OpenAlex, Crossref, arXiv-API and Semantic-Scholar endpoints were blocked during the initial search. OpenAlex/Crossref/arXiv became reachable on 27 October; supplemental searches and reference metadata checks are documented below and in `search_log.md`.
* **Inclusion criteria.**
  * (i) Published or posted 2023-2026.
  * (ii) Addresses prompt injection against LLM-integrated applications or tool-using agents (attack, benchmark or defence), *or* human oversight / permissions / confirmation for AI agents.
  * (iii) Has a retrievable bibliographic record.
* **Exclusion criteria.** Jailbreaking without an injection or agent component; vendor blogs; papers without a verifiable record.
* **Foundational exceptions.** Pre-2023 works are cited only for theory and instruments: automation trust, warning science, habituation, SDT, information flow, least privilege, NASA-TLX, SUS and trust scales.

### Supplemental index search and novelty reassessment (27 October 2026)

After the environment's scholarly API domains became reachable, we ran a
supplemental search against OpenAlex on 27 October 2026. This is a documented
update to the earlier rapid review, not a second-reviewer systematic review.
Eight queries (below) each requested the first 50 ranked works dated
2023-01-01 through 2026-10-27: 400 records returned, 342 unique OpenAlex work
IDs after deduplication. The query result totals were 4,349; 1,295; 5,817;
15,539; 2,765; 155; 791; and 16,810, respectively. These are ranked samples,
not exhaustive database results. Results were title/abstract screened by one
reviewer; the original search records and reference-level metadata audit are
in `openalex_metadata_audit.csv` and `search_log.md`.

| Query key | Query | OpenAlex total | Retrieved |
|---|---|---:|---:|
| agent_prompt_injection | indirect prompt injection AI agents tool use defense | 4,349 | 50 |
| agentdojo_defense | AgentDojo prompt injection defense agent benchmark | 1,295 | 50 |
| agent_security_benchmark | agent security benchmark prompt injection attacks defenses | 5,817 | 50 |
| human_agent_permissions | user permission decisions AI agents human computer interaction | 15,539 | 50 |
| human_prompt_injection_ui | prompt injection interface user study human oversight agent | 2,765 | 50 |
| confirmation_risk_cards | prompt injection risk card confirmation UI agent | 155 | 50 |
| provenance_tool_authorization | provenance tool authorization LLM agents human oversight | 791 | 50 |
| tool_call_security_warnings | AI agent tool calls security warning usability | 16,810 | 50 |

This search surfaced a direct novelty threat that changes our gap statement:
Su, Rao, and Ma's 2026 Risk Cards article (DOI
`10.51903/ijgd.v4i1.3699`) describes source-trust, sensitivity and permission
cues, data-flow arrows, consequence previews, a risk badge, and safer
alternatives in a prompt-injection confirmation UI. Its abstract reports an
automated oversight proxy over 13,068 UI samples from 18 AgentDojo pipeline
runs. Those are not human-participant outcomes. The article therefore
precludes claiming CLEAR as the first provenance-aware confirmation card or
human-facing prompt-injection interface. CLEAR's narrower candidate novelty is
the executable mediator, conditional monotonicity property for its risk tier,
state-predicate-based replay outcomes, and joint reporting of security,
utility, and interruption burden. CLEAR's human-factor results are also
simulated, so this is a systems/method contribution, not evidence that the UI
improves human decisions.

Recent permission research further narrows the gap. Yan (2026; 113
participants) compares per-action approval, automated review, and user-authored
rules; Salerno et al. (2026; 18 interviews and 115 survey participants) study
practitioners' permission decisions; and Michael and Roesner (2026) survey 21
user-level permission systems and five commercial agents. These works address
agent overreach, permissions, and reviewability but do not evaluate
argument-level provenance under prompt injection. Risk Cards is the direct
prompt-injection interface antecedent and must be treated separately from
these permission studies.

The Risk Cards publisher PDF URL returned HTTP 403 from this runtime. The
comparison above is limited to Crossref metadata and the OpenAlex-recorded
abstract; no claims about details beyond that abstract are made. Its publisher
host was added to the environment configuration draft for review.

### Queries (Consensus)

| # | Query | Top-10 records screened | Included |
|---|---|---|---|
| 1 | indirect prompt injection LLM agents defense tool calls | 10 | 9 |
| 2 | user permissions for AI agents interfaces enforcement human approval prompts | 10 | 9 |
| 3 | defeating prompt injections by design CaMeL capabilities control flow data flow | 10 | 6 |
| 4 | habituation to security warnings polymorphic warnings fMRI | 10 | 3 |
| 5 | Not what you've signed up for: compromising real-world LLM-integrated applications ... | 10 | 5 |
| 6 | AgentDojo dynamic environment evaluate prompt injection attacks defenses LLM agents | 10 | 8 |
| 7 | StruQ structured queries SecAlign preference optimization instruction hierarchy ... | 10 | 4 |
| 8 | The Instruction Hierarchy: training LLMs to prioritize privileged instructions | 10 | 1 |
| 9 | Progent programmable privilege control LLM agents | 10 | 3 |
| 10 | design patterns for securing LLM agents against prompt injections | 10 | 5 |
| 11 | To trust or to think: cognitive forcing functions ... | 10 | 2 |
| 12 | Humans and automation: use, misuse, disuse, abuse; trust in automation ... | 10 | 2 |

Two further Consensus queries (user-study-specific) failed with a rate limit.
Web searches (about 25) were used to locate specific records and to look for
user studies of prompt-injection warnings. None was found besides the agent-permission studies listed below.

## Taxonomy: where is the human?

| Human role | Representative work | What the human sees | Burden reported? |
|---|---|---|---|
| **Absent** (model-level) | Spotlighting; Instruction Hierarchy; StruQ; SecAlign; Meta-SecAlign; PromptArmor; detectors | nothing | n/a |
| **Absent** (system-level, auto-enforced) | CaMeL; FIDES; f-secure; MELON; Task Shield; IPIGuard; DRIFT; AttriGuard; LLMbda; CSAgent | nothing (blocked calls fail) | no |
| **Pre-authorisation** (policy / scope set before run) | Progent; ClawGuard (user-confirmed rule set); MiniScope; ToolFence; Authenticated delegation; Yan 2026 POLICY | rules / scopes | MiniScope (simulated confirmations); Yan 2026 (prompts) |
| **Runtime confirmation** | Magentic-UI action guards (irreversibility labels + LLM judge); MCP-style approve/deny; Yan 2026 HITL; Janus permission assistants; Su et al. 2026 Risk Cards | generic call, or card with trust labels | Janus (synthetic responders); Su (proxy) |
| **Audit / post-hoc** | Logging and undo in commercial agents (Ge 2026; Michael 2026 survey) | timeline | no |
| **CLEAR (this work)** | pre-authorisation (envelope) + risk-adaptive runtime confirmation + audit | argument-level lineage, reasons, forcing check | yes: dialogs per task, recall/FER, simulated end-to-end ASR |

## Key findings that shape the gap

1. **Attack surface persists.** Template attacks still hijack frontier agents (AgentDojo results table). Adaptive and optimised attacks break model-level and detector defences (Zhan 2025; Pandya 2025; AutoInject 2026; AutoDojo 2026; Hofer 2026).
2. **System-level defences trade utility for guarantees.** CaMeL solves 77% of tasks with guarantees, against 84% undefended (its own abstract). LLMbda reports that CaMeL's policy checks halve its utility in their setting. Wang et al. 2026 (SoK) show that many defences look effective by suppressing context-dependent inputs. Abdelnabi et al. 2026 argue that context-dependent flows are fundamentally ambiguous.
3. **Humans are the de-facto fallback, and they struggle.**
   * Warning effectiveness depends on design and frequency (Egelman 2008; Sunshine 2009; Akhawe & Felt 2013).
   * Habituation sets in quickly and generalises across similar-looking notifications (Anderson 2015; Vance 2018; Vance 2025).
   * In agent settings, users approve overreach (Yan 2026) and lack visibility into what lies behind an action (Salerno 2026).
4. **Explanations alone can increase overreliance** (Bansal 2021). Cognitive forcing reduces overreliance at a cost in subjective ratings (Buçinca 2021). Explanations help when they lower the cost of verification (Vasconcelos 2023). This motivates showing *verifiable provenance* (where a value came from) rather than an AI's opinion. It also motivates reserving forcing for the rare highest-risk case.
5. **Closest prior work.** Su et al. 2026 (Risk Cards) is a direct antecedent for prompt-injection confirmation UI and AgentDojo-derived evaluation. We make no novelty claim for risk cards, provenance cues, consequence previews, or confirmation. CLEAR's narrower distinction is an executable tool-call mediator, argument lineage through supported transformations, a conditional escalation-floor property, and replay of enforcement decisions against task-state predicates. Its user outcomes remain untested; the habituation analysis is simulation only.

## Revised gap statement

The review does not support an absence claim for prompt-injection warning
interfaces: Risk Cards is a direct antecedent. The defensible gap is that the
closest identified interface paper reports an information-exposure proxy,
whereas CLEAR implements a tool-call mediator and replays its decisions
against stateful task/security predicates, while reporting utility and
interruption burden. CLEAR adds an argument-lineage mechanism and a conditional
risk-floor property. Neither study includes human participants. A new human
study is required to test whether the interface changes users' decisions.
