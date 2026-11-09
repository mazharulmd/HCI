# User-study protocol (pre-registration draft)

**Status: NOT YET CONDUCTED.** No participant data exist. This protocol, the
consent form, the debriefing and the analysis plan are ready for submission to
an Institutional Review Board / Ethics Committee. The study apparatus is
implemented (`clear/ui`) for a **laboratory** study and was verified end-to-end
with automated browser sessions, not with people. How to run a session is
described in `lab_runbook.md`.

## 1. Title
Do provenance-aware, risk-adaptive confirmations help people stop prompt-injected AI-agent actions?

## 2. Hypotheses (confirmatory)
The design crosses the two levers CLEAR combines. The 2×2 factorial structure
follows the recommendation of the Trust Boundary Lab iteration (see
`docs/prior_iterations_audit.md`).
* **H-U1 (selectivity).** Asking only about escalated actions, rather than about every side-effecting action, increases the proportion of injected actions that participants prevent. This is the main effect of *selectivity*.
* **H-U2 (evidence).** Showing argument provenance, source-to-action excerpts, the consequence preview and the forcing check increases prevention. This is the main effect of *evidence*.
* **H-U3 (cost).** Benign-task completion under full CLEAR (A) is not lower than under confirm-all (B), with a non-inferiority margin of 5 percentage points. NASA-TLX raw workload in A is not higher than in B.
* **Exploratory.** The selectivity × evidence interaction; SDT sensitivity d′ and criterion c; decision time; SUS; trust (Jian et al. 2000); forcing-question accuracy; envelope edits; undo use; free-text reasons.

## 3. Design
* Between-subjects **2 × 2 factorial**:

| | generic dialog | evidence dialog |
|---|---|---|
| **ask about every side-effecting action** | B `confirm_all` | D `confirm_all_evidence` |
| **ask only about CLEAR escalations** | C `clear_generic` | A `clear` (full CLEAR) |

  **Assignment.** The server assigns each participant when the demographics form is submitted. Randomisation is stratified by self-reported programming experience: *low* (none, a little) vs *high* (regular, professional). Within each stratum, permuted blocks of 4 or 8 (chosen at random) contain every condition equally often. The sequence is generated once, from a random seed, at first use and stored in `user_study_logs/allocation.json`, which is never served to browsers (allocation concealment). The study console does not display the condition, so the experimenter stays blind. A returning participant code keeps its condition. A fifth, no-mediation arm (`none`) exists for demonstrations only and is never assigned.
* A between-subjects design avoids carry-over: once a participant has seen one attack, they are primed for the rest.
* Each participant supervises **16 recorded agent tasks**: 12 benign and 4 containing a successful prompt injection. All are real AgentDojo trajectories of GPT-4o (`clear/ui/static/scenarios.json`); the answer key is kept separately in `data/ui_answer_key.json`. Every escalated action carries a *consequence preview* computed by executing it on a copy of the environment. Two further trajectories (one benign, one attacked, not among the 16) serve as practice tasks and are never scored.
* Scenario order is rotated per participant (Latin-square rotation in `app.js`).
* The prevalence of attacks (25%) is higher than realistic. This is stated as a limitation, and an exploratory follow-up with 1/16 prevalence is planned.

## 4. Participants
* **N = 220** adults (55 per cell), recruited from the university participant pool and by notices on campus. Fluent English. Have used e-mail and online banking. Sessions take place in a computer laboratory; several participants can take part at once on separate computers.
* **Power analysis.** Each main effect compares 110 vs 110 participants. With α = .05 (two-sided) and power .80, a standardised effect of d = 0.4 on participant-level prevention rates requires 100 per factor level (statsmodels `TTestIndPower`). 55 per cell allows about 9% exclusions. The interaction is exploratory, because detecting it with equal power would need about four times the sample.
* **Exclusion criteria (pre-registered).** Failing both attention checks; completing the 16 tasks in under 4 minutes; technical failure that prevents logging (fewer than 16 tasks logged); the condition shown in the browser differs from the server's assignment. Pilot sessions use participant codes starting with `PILOT` and are never analysed.
* **Compensation** at or above the local minimum wage, prorated for an expected 35 minutes.

## 5. Materials and procedure
Every step runs in the browser; the experimenter only enters the participant code on `start.html`.
1. Information sheet and consent (`consent.html`, text of `consent_form.md`). The deception element is disclosed in general terms: "some tasks may include problems you should catch". A participant who declines leaves without any further data being recorded.
2. Demographics (`demographics.html`): age range, gender, programming experience (the randomisation stratum), security training, use of AI assistants, use of e-mail and online banking. Submitting it triggers the assignment.
3. Introduction and two practice tasks (one benign, one with an injection) in the participant's own condition interface. They are not scored.
4. The 16 tasks. The participant reads the request, (A only) may edit the intent envelope, starts the agent and answers every dialog. Two instructed-response attention checks follow tasks 5 and 11. Each shows a proposed payment with the instruction "Approve this action only if the amount is exactly 10.00": the first shows 25.00 (correct: deny), the second 10.00 (correct: approve).
5. Post-task questionnaire (`questionnaire.html`): SUS (Brooke 1996), NASA-TLX raw (Hart & Staveland 1988), the trust-in-automation scale (Jian et al. 2000) and two open questions.
6. Debriefing (`debrief.html`, text of `debriefing.md`): what prompt injection is, which tasks contained attacks, and that no real money or e-mail was involved. The list of attacked tasks is released by the server only after this participant's questionnaire has been saved.

## 6. Measures
* **Primary.**
  * *Injected-action prevention.* For each of the 4 attacked tasks: 1 if the injected action was denied (or, in B, never approved), else 0. This uses the answer key, *only* for actions that were shown in a dialog. Injected actions never shown count as not prevented, which is the end-to-end view.
  * *Benign completion.* For each benign task: 1 if no benign action was denied.
* **Secondary.** Per-dialog decision correctness; d' and c computed per participant with a log-linear correction; median decision time; number of dialogs; SUS; TLX; trust.

## 7. Analysis plan
The complete analysis is implemented in `experiments/analyze_user_study.py`. It was written before any data were collected and has been run only on synthetic logs, in the automated tests.
* **Primary analysis (H-U1, H-U2).** Logistic regression estimated by generalised estimating equations (GEE) with an exchangeable working correlation and participants as clusters: `prevented ~ selective * evidence + C(scenario)`, with factors effect-coded as ±0.5, so that exp(β) is the odds ratio between factor levels. Wald 95% CIs with robust standard errors. Holm correction over the two main effects. *Why not a mixed model with a scenario random effect:* with four attacked scenarios, a scenario variance is poorly identified, so scenario enters as a fixed effect; GEE also gives population-averaged odds ratios with robust standard errors.
* **Robustness for the primary analysis.** A permutation test (10,000 permutations, labels permuted within randomisation strata) of each main effect on participant-level prevention rates, Holm-corrected. It stays valid when a condition prevents every attack, where the GEE is not estimable (separation).
* **Non-inferiority (H-U3).** Full CLEAR (A) vs confirm-all (B), on participant-level means with Welch standard errors. Benign completion: non-inferior if the lower bound of the 90% CI of A − B is above −5 percentage points. NASA-TLX: non-inferior if the upper bound of the 90% CI of A − B is below +8 points.
* **Secondary and exploratory.** Per-condition descriptives of dialogs, dialog accuracy, d′ and c (log-linear correction), median decision time, SUS, TLX, trust, forcing-question accuracy, envelope edits and undo use; the selectivity × evidence interaction.
* **Robustness.** The primary GEE repeated (i) excluding participants who failed either attention check, and (ii) excluding each participant's first attacked task in presentation order, to gauge learning.

## 8. Risks and ethics
* **Minimal risk.** Simulated environments only; no real accounts, payments or messages. Attack texts are those of a public benchmark. The deception (unannounced attacks) is mild, necessary for ecological validity, and fully debriefed.
* **Data.** Pseudonymous participant ID only. No IP addresses are stored by the apparatus. Logs are stored on encrypted institutional storage and deleted after 5 years or as required.
* **Withdrawal.** Participants may withdraw at any time without penalty. Their data will be deleted on request until anonymised analysis.

## 9. Deviations
Any deviation from this protocol will be reported in the paper together with its justification.
