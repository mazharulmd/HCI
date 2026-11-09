# Research plan and review protocol

## Scope and gap

The target interaction is an AI agent that reads user-authorized external content and proposes a tool call whose requested action or permission may be induced by that content. The study boundary is the user's decision before the call executes. Model-level injection resistance, general AI literacy, and production connector security are out of scope for this first study.

The working gap is the limited understanding of how provenance cues, action-specific risk explanations, least-privilege scope, and an explicit human checkpoint work together at the moment of tool authorization. The contribution is to operationalize these as a source-to-action review pattern and measure both security decisions and interaction costs. This gap is **provisional**: the planned 2023–2026 review is incomplete because scholarly indexes were inaccessible from the current runtime (HTTP 403); a domain-access draft was saved for environment review. No claim of novelty should be made until screening and duplicate-work comparison are finished.

## Systematic review plan (not yet completed)

- Sources: ACM Digital Library, IEEE Xplore, USENIX proceedings, SOUPS, arXiv (clearly separated from peer-reviewed work), OpenAlex, Crossref, and Semantic Scholar.
- Window: 2023-01-01 through 2026-10-27 (search date; the current year is partial).
- Search families: `("prompt injection" OR "indirect prompt injection") AND (agent OR tool OR browser OR email)`; `("AI agent" OR "LLM agent") AND (interface OR interaction OR user OR trust OR consent)`; `("tool use" AND (permission OR authorization OR provenance) AND (LLM OR agent))`.
- Include: English full papers, peer-reviewed or clearly labeled preprints, that evaluate prompt-injection attacks/defenses in LLM applications or study human interaction with AI agents, trust, permission, or security warnings.
- Exclude: model-only prompt attacks without a tool/action boundary, duplicate versions (retain the archival version and cross-reference preprint), non-research commentary, and unrelated prompt engineering.
- Record: database/query/date, raw result count, deduplicated count, inclusion decision and reason, study task, threat model, intervention, participants, outcome, and limitation. Two reviewers should screen independently and resolve disagreements; report agreement and a PRISMA-style flow.
- Synthesis: distinguish model/system defenses from user-facing controls; map interventions to provenance visibility, permission granularity, timing, user workload, and attack outcome. Compare to existing warning and confirmation systems before asserting novelty.

## Questions and preregisterable hypotheses

- **RQ1:** How do source provenance and action-specific risk explanations affect detection of tool-call requests induced by untrusted content?
- **RQ2:** What security benefit and workload cost follows from explicit, scoped confirmation before high-impact actions?
- **RQ3:** Which interface cues help people distinguish benign external content from instructions that conflict with the user's intent?
- **H1:** A combined provenance + permission + risk explanation + confirmation condition will improve attack rejection accuracy versus a no-intervention baseline.
- **H2:** A risk-only warning will cause more false blocks of benign high-impact actions than a source-to-action review that also shows the user's requested scope.
- **H3:** Review controls will increase decision time and perceived workload; the increase will be smaller for read-only than externally visible/destructive actions.

These are hypotheses, not observed results. A preregistration should specify primary outcomes, exclusions, sample-size rationale, randomization, model/scenario version hashes, and analysis before recruitment.

## Planned factorial evaluation

Use a within-subject, counterbalanced 2x2 design: provenance present/absent × action-risk rationale and explicit authorization present/absent, plus a no-intervention baseline. Randomize scenario order and balance scenario variants across participants. Avoid showing the attack label. The current scripted `risk_badge`, `provenance_consent`, and `combined` policies are engineering baselines only; a human study must present these conditions as UI variants with identical underlying agent suggestions. The current rule policy is not a comparable model-based defense.

Primary outcomes: attack success rate (fraction of malicious proposed calls accepted), defense effectiveness (fraction blocked), decision accuracy against the task-specific authorization policy, and benign false-positive block rate. Secondary outcomes: response time, comprehension, confidence calibration, NASA-TLX workload, and perceived control/trust. Report latency as interface response time separately from human decision time. Use participant and scenario random effects for binary outcomes (mixed-effects logistic regression); analyze time with an appropriate robust/log-time mixed model; report estimates, confidence intervals, and multiplicity handling. Sample size must be set by power simulation using plausible pilot effect sizes, not selected after looking at outcomes.

## Operational metric definitions

- Attack success rate = malicious proposals accepted / malicious proposals shown.
- Defense effectiveness = malicious proposals blocked / malicious proposals shown.
- Benign false-positive rate = benign proposals blocked / benign proposals shown.
- Decision accuracy = decisions matching the pre-specified user-intent authorization label / all decisions.
- Workload: NASA-TLX subscales and overall score collected after each block.
- Latency: review rendering-to-choice milliseconds; report median and distribution by condition.

Current machine evaluation only computes deterministic attack success, defense effectiveness, benign block rate, and label accuracy over constructed fixtures. It does not measure time, workload, statistical significance, or user recognition.
