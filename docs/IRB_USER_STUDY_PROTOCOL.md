# IRB-Ready Human-Subjects Experimental Protocol: Evaluating PROV-Guard Against Indirect Prompt Injection

## 1. Study Title & Overview
- **Study Title:** Human-Computer Interaction for Secure AI Tool Usage: Evaluating Causal-Provenance and Adaptive-Friction Design Patterns Against Indirect Prompt Injection
- **Design:** Within-subjects repeated-measures Latin-square design across interactive AI agent defense interfaces, paired with stratified operator expertise blocks (Novice, Intermediate, Security-Aware).
- **Target Sample Size:** $N = 48$ adult participants ($16$ per expertise stratum), providing $>0.95$ statistical power at $\alpha = 0.01$ to detect medium-to-large effect sizes ($d \ge 0.60$).

## 2. Ethical Safeguards & Informed Consent
1. **Sandboxed Execution Environment:** All tool calls (`send_email`, `execute_wire_transfer`, `execute_shell_command`, `share_file_external`, `delete_calendar_events`) execute strictly inside an isolated, in-memory browser simulation (`ui/prov_guard_workbench.html`) with synthetic enterprise personas and dummy credentials. Zero personal data or real user accounts are accessed.
2. **Deception & Debriefing:** Participants are briefed to act as an enterprise operations analyst collaborating with an AI assistant to complete routine productivity tasks accurately and securely. At the conclusion of the session, participants receive a full educational debriefing explaining the five indirect prompt injection families (Direct Override, Context Framing, Obfuscated Payloads, Cross-Tool Chaining, and Semantic Goal-Mimicry).
3. **Data Privacy:** Only anonymized trial reaction times (ms), binary approval/rejection choices, and post-condition NASA-TLX ratings are logged.

## 3. Experimental Procedure
1. **Screening & Stratification (5 min):** Participants complete a 6-item technical familiarity questionnaire to classify into Novice (general office users), Intermediate (software/IT practitioners), or Security-Aware (cybersecurity/AI safety familiarity).
2. **Interactive Task Blocks (35 min):** Participants evaluate sequential AI agent tool proposals using `ui/prov_guard_workbench.html` across counterbalanced interface conditions (`B2_STATIC_BANNER`, `B3_BINARY_MODAL`, `PROV_GUARD_FULL`, and pattern ablations).
3. **Workload & Usability Assessment (10 min):** After each block, participants complete the 6-subscale NASA Task Load Index (NASA-TLX: Mental Demand, Physical Demand, Temporal Demand, Performance, Effort, Frustration) and a 10-item System Usability Scale (SUS).
4. **Statistical Analysis Plan:** Non-parametric omnibus Kruskal-Wallis tests followed by pairwise Mann-Whitney $U$ / Wilcoxon signed-rank tests with Holm-Bonferroni step-down multiple-testing correction, reporting Cohen's $d$, Cliff's $\delta$, and Signal Detection Theory sensitivity ($d'$) and criterion bias ($c$).
