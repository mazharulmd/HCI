# Proposed user-study protocol (not preregistered)

**Status: NOT SUBMITTED OR CONDUCTED.** No participant data exist. This protocol, the
consent form, the debriefing and the analysis plan are drafts for review by an
Institutional Review Board / Ethics Committee before recruitment. The study apparatus is
implemented (`clear/ui`) and was verified end-to-end with an automated
browser test (`figures/ui_*.png`), not with people.

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

  Random assignment is stratified by self-reported programming experience. A fifth, no-mediation arm (`none`) is optional and is used only for describing the baseline.
* A between-subjects design avoids carry-over: once a participant has seen one attack, they are primed for the rest.
* Each participant supervises **16 recorded agent tasks**: 12 benign and 4 containing a successful prompt injection. All are real AgentDojo trajectories of GPT-4o (`clear/ui/static/scenarios.json`); the answer key is kept separately in `data/ui_answer_key.json`. Every escalated action carries a *consequence preview* computed by executing it on a copy of the environment.
* Scenario order is rotated per participant (Latin-square rotation in `app.js`).
* The prevalence of attacks (25%) is higher than realistic. This is stated as a limitation, and an exploratory follow-up with 1/16 prevalence is planned.

## 4. Participants
* **N = 220** adults (55 per cell), recruited via a crowdsourcing platform or a university pool. Fluent English. Have used e-mail and online banking. Desktop browser.
* **Provisional recruitment target, not a power analysis.** N = 220 is an initial planning target. The earlier independent-samples calculation does not establish power for the proposed mixed-effects logistic primary analysis. Before recruitment, run a simulation-based power analysis using justified baseline rates, participant/scenario variance, and the final model.
* **Proposed exclusion criteria (to preregister before recruitment).** Failing both attention checks; completing the 16 tasks in under 4 minutes; technical failure that prevents logging.
* **Compensation** at or above the local minimum wage, prorated for an expected 35 minutes.

## 5. Materials and procedure
1. Information sheet and consent (`consent_form.md`). The deception element is disclosed in general terms: "some tasks may include problems you should catch".
2. Demographics and a short security-behaviour questionnaire (SeBIS is optional, pending licence check).
3. Training: two practice tasks (one benign, one with an obvious injection) using the participant's condition interface.
4. The 16 tasks. The participant reads the request, (A only) may edit the intent envelope, starts the agent and answers every dialog. Attention checks are embedded in two benign tasks ("approve this action only if the amount is 10.00").
5. Post-task questionnaire (`clear/ui/static/questionnaire.html`): SUS (Brooke 1996), NASA-TLX raw (Hart & Staveland 1988), the trust-in-automation scale (Jian et al. 2000) and two open questions.
6. Debriefing (`debriefing.md`): what prompt injection is, which tasks contained attacks, and that no real money or e-mail was involved.

## 6. Measures
* **Primary.**
  * *Injected-action prevention.* For each of the 4 attacked tasks: 1 if the injected action was denied (or, in B, never approved), else 0. This uses the answer key, *only* for actions that were shown in a dialog. Injected actions never shown count as not prevented, which is the end-to-end view.
  * *Benign completion.* For each benign task: 1 if no benign action was denied.
* **Secondary.** Per-dialog decision correctness; d' and c computed per participant with a log-linear correction; median decision time; number of dialogs; SUS; TLX; trust.

## 7. Analysis plan
* **Primary analysis.** Mixed-effects logistic regression, `prevented ~ selective * evidence + (1|participant) + (1|scenario)`, with effect-coded factors. Main effects are tested with Holm correction over the two confirmatory tests. Odds ratios are reported with 95% CIs (Wald and parametric bootstrap).
* **Non-inferiority (H-U4).** Two one-sided tests on the participant-level benign completion rate (margin 5 pp). TLX: Welch t-test, plus TOST with a margin of 8 TLX points.
* **Robustness.** Including participants who failed one attention check. Excluding the first attacked task, to estimate learning.
* Final analysis code will be written against the log schema emitted by `clear/ui/server.py` before data collection and archived with the preregistration.

## 8. Risks and ethics
* **Minimal risk.** Simulated environments only; no real accounts, payments or messages. Attack texts are those of a public benchmark. The deception (unannounced attacks) is mild, necessary for ecological validity, and fully debriefed.
* **Data.** Pseudonymous participant ID only. No IP addresses are stored by the apparatus. Logs are stored on encrypted institutional storage and deleted after 5 years or as required.
* **Withdrawal.** Participants may withdraw at any time without penalty. Their data will be deleted on request until anonymised analysis.

## 9. Deviations
Any deviation from this protocol will be reported in the paper together with its justification.
