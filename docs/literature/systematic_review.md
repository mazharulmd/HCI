# Structured literature review (2023 – Oct 2026)

**Type.** A structured *rapid* review with a documented search, explicit inclusion
criteria and a taxonomy. We do **not** claim a full PRISMA systematic review,
because screening was done by a single reviewer (the research agent) and the
search was limited to two discovery services. All queries are listed below so
the search can be re-run and extended.

## Search protocol

* **Date of search:** 26 October 2026.
* **Discovery services.**
  1. Consensus (semantic search over Semantic Scholar / OpenAlex / PubMed records). Each query returns the top 10 records with title, authors, year and venue.
  2. A general web search engine, used for publisher pages (ACM DL, USENIX, IEEE), arXiv listings and DBLP-like pages.
* **Not reachable from the research environment.** The OpenAlex, Crossref, arXiv-API and Semantic-Scholar endpoints were blocked by the sandbox network policy (HTTP 403). Records were therefore verified through the two services above. See `verification_log.md`.
* **Inclusion criteria.**
  * (i) Published or posted 2023-2026.
  * (ii) Addresses prompt injection against LLM-integrated applications or tool-using agents (attack, benchmark or defence), *or* human oversight / permissions / confirmation for AI agents.
  * (iii) Has a retrievable bibliographic record.
* **Exclusion criteria.** Jailbreaking without an injection or agent component; vendor blogs; papers without a verifiable record.
* **Foundational exceptions.** Pre-2023 works are cited only for theory and instruments: automation trust, warning science, habituation, SDT, information flow, least privilege, NASA-TLX, SUS and trust scales.

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
5. **Closest prior work.** Su et al. 2026 (Risk Cards) also targets the confirmation interface under prompt injection with AgentDojo traces. CLEAR differs in four ways. (a) It contributes a formal, ablated risk model with an attacker-text-independent escalation floor. (b) It recomputes environment outcomes rather than an information-exposure proxy. (c) It measures and budgets interruptions and compares against system-level and published defences with paired tests. (d) It models habituation explicitly and provides a forcing tier.

## Gap statement

No prior work jointly (i) decides *when* to involve the human, using provenance-aware contextual risk with a formal floor, (ii) designs *what* the human sees at argument level, and (iii) evaluates the resulting human-machine system on real attacked agent trajectories in terms of security, utility **and** human burden. This study addresses these three gaps.
