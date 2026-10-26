# Research design

**Title.** Human-Computer Interaction for Secure AI Tool Usage: Design Patterns Against Prompt Injection

**One-sentence summary.** We design, implement and evaluate *CLEAR*, a human-centred
mediation layer for LLM-agent tool calls. It escalates only the actions whose
provenance and context make them risky. When it does, it shows the user *where
each argument came from* and *why the action is suspect*, and it uses a stronger,
differently-shaped interaction (cognitive forcing) for the highest-risk actions.

## 1. Problem

Indirect prompt injection lets text inside data (e-mails, web pages, files,
channel names, reviews) take over a tool-using agent. Two families of defences
exist.

* **Model/prompt-level defences** (spotlighting, sandwiching, instruction
  hierarchy, StruQ/SecAlign/Meta-SecAlign, detectors) reduce but do not
  eliminate attack success. Adaptive attacks break them.
* **System-level defences** (CaMeL, FIDES, f-secure, Progent, MELON, Task
  Shield, IPIGuard, ClawGuard, AttriGuard, ToolFence, MiniScope) enforce
  policies outside the model. Their strict forms lose utility on the many
  legitimate tasks whose arguments *must* come from untrusted data, such as
  paying the IBAN in a bill or replying to the sender of an e-mail.
  Abdelnabi et al. (2026) argue that this tension is irreducible:
  context-dependent flows can only be judged in context.

Every deployed agent therefore ends up asking the **human** to resolve the
residual ambiguity, through permission prompts and confirmation dialogs. Usable
security has shown for two decades that such prompts fail when they are
frequent, uninformative or habituating (Egelman 2008; Sunshine 2009; Felt
2012; Akhawe & Felt 2013; Anderson 2015; Vance 2018, 2025). The first agent
studies point the same way. Yan (2026, N=113) found that people approved many
overreach actions, Salerno (2026) found that practitioners lack visibility of
what lies behind an action, and Janus and MiniScope (2025/26) report permission
fatigue.

## 2. Research gaps (from the systematic review, `docs/literature/systematic_review.md`)

| # | Gap | Evidence |
|---|---|---|
| G1 | System-level defences treat the human as either absent (auto-deny) or a generic fallback ("requires approval"). What evidence the human sees, and how often they are interrupted, is unspecified and unmeasured. | CaMeL, Progent, ClawGuard, MiniScope report ASR/utility; none report interruption burden together with evidence design. |
| G2 | HCI work on agent permissions studies over-reach, preference elicitation and fatigue, but not **adversarial provenance**: whether the action was caused by injected content, and which argument came from where. | Yan 2026; Wu et al. S&P 2026; Janus 2026; Michael et al. 2026 survey; Ge CHI EA 2026; Salerno 2026. |
| G3 | The closest work (Su et al. 2026, Risk Cards) proposes a confirmation card with source-trust labels evaluated on AgentDojo traces. It uses a *deterministic information-exposure proxy*. It does not recompute environment outcomes, compare against system-level baselines, budget interruptions, or model habituation. | Su et al. 2026 |
| G4 | Defence evaluations do not report **user burden** (dialogs per task), **escalation precision/recall**, or the **joint human-machine** attack success that results when a fallible human answers the dialogs. | AgentDojo-based evaluations (MELON, Task Shield, IPIGuard, Progent, ...); Khan et al. 2026 call for richer reporting. |

## 3. Contributions

1. **Systematic review and taxonomy** of 2023-2026 prompt-injection defences by the *role of the human* (absent / pre-authorisation / runtime confirmation / audit) and the *evidence presented*.
2. **CLEAR design patterns** (P1-P6, Sec. 5) with a formal risk model and an **escalation-floor guarantee** (Proposition 1). The guarantee is independent of attacker-controlled text.
3. **Open implementation**: mediation engine, AgentDojo trace replayer, baselines, interactive console, user-study apparatus, and 49 automated tests.
4. **Large-scale, environment-grounded evaluation** on real attacked trajectories of 20+ LLMs and published defences. It recomputes AgentDojo's own utility and security predicates after mediation and reports burden, ablations, a detector-evading attacker and latency, with significance tests.
5. **Habituation-aware human-in-the-loop analysis**: a parametric SDT model that converts escalations into end-to-end risk under fallible users. It is *hypothesis-generating*. A **pre-registered user-study protocol** tests its predictions with people.

## 4. Research questions and hypotheses

* **RQ1 (Security).** How much does provenance-aware, risk-adaptive mediation reduce attack success relative to undefended agents, published model/prompt-level defences, and tool-call-level baselines?
  * *H1.* With an ideal user, CLEAR's ASR on held-out episodes is lower than the undefended agent, the task-scoped allowlist and the strict information-flow policy, and statistically indistinguishable from confirm-all.
* **RQ2 (Burden & utility).** What interruption burden and utility cost does it impose?
  * *H2.* CLEAR raises significantly fewer confirmation dialogs per benign task than confirm-all.
  * *H3.* In automatic mode (escalations denied), CLEAR preserves more benign utility than confirm-all-deny. With an ideal user it loses no utility.
* **RQ3 (Mechanism).** Which components carry the effect, and does it survive an attacker who evades text-based detection?
  * *H4.* Removing argument provenance raises ASR. Removing the instruction-likeness signal does not raise ASR much (Proposition 1), whereas a lexical detector fails completely against the same attacker.
* **RQ4 (Human factors).** Given fallible, habituating users, how do selectivity and evidence affect end-to-end compromise and decision quality?
  * *H5 (simulation; user study).* Across most of the plausible parameter space, end-to-end ASR is lower with CLEAR than with confirm-all, because fewer dialogs slow habituation and forcing dialogs resist it.
  * *H6 (user study only).* Provenance evidence raises users' sensitivity d' for injected actions without raising NASA-TLX workload. Confirmation dialogs for benign actions are approved at least as often as with generic dialogs.

## 5. Architecture and design patterns

```
 user prompt ──► [P1 Intent envelope compiler] ──► envelope (user-editable)
                                                       │
 LLM agent ──proposed tool call──► [CLEAR mediator] ◄──┘
                                       │  ▲
          tool outputs (+trust label)──┘  │ provenance ledger [P2]
                                       │
              features: s, τ, κ, δ, ι  │  [P3 contextual risk]  R = s·(1-Π(1-w_i x_i))
                                       ▼
            ALLOW ─ NOTIFY ─ CONFIRM ─ FORCE      [P4 risk-adaptive escalation]
                       │        │        │
                 ambient   provenance   cognitive-forcing check [P5]
                 notice    dialog       ("where did this IBAN come from?")
                 + undo                 + polymorphic visual
                                       │
                         audit timeline + undo [P6]
```

* **P0 Declared capabilities** (tool manifest: capability, sensitivity, reversibility, target/content/value arguments, output trust).
* **P1 Intent envelope.** The task-scoped capabilities and entities compiled from the prompt alone, shown to and editable by the user.
* **P2 Argument-level lineage.** Every argument is attributed to *your request / trusted record / external content (which) / nowhere*, with fail-closed endorsement.
* **P3 Contextual risk.** Interpretable features combined by noisy-OR and weighted by harm potential.
* **P4 Risk-adaptive escalation** with an interruption budget. Irreversible actions are never silently executed above the notice tier.
* **P5 Differentiated, forcing confirmation** for the highest tier, so that habituation to routine dialogs does not transfer.
* **P6 Audit and undo.** An ambient timeline of everything executed, with undo for reversible actions.

## 6. Scope and measurable outcomes

* **Environment.** AgentDojo (banking, slack, travel, workspace; 97 user tasks, 629 security cases per attack).
* **Data.** Real traces of 20+ LLM agents and four published defences from the AgentDojo repository (pinned commit), replayed in AgentDojo's own environments.
* **Primary outcomes.** ASR, utility under attack, benign utility, dialogs per benign task.
* **Secondary outcomes.** Escalation recall, false escalation rate, AUROC, tier distribution, latency.
* **Human outcomes.** Decision accuracy and d', response time, SUS, NASA-TLX, trust (Jian et al.). These are simulation (RQ4) and user-study protocol only.

## 7. Frozen configuration and data splits

* **Development split.** GPT-4o on banking + slack, the only data inspected while designing. Changes made on it are logged in `docs/development_log.md`.
* **Held-out.** Travel + workspace for every model, and all suites for every other model and defence pipeline.
* The configuration was committed before any held-out result was computed (git history).

## 8. What this study does not do (and why)

* **No human-subject data were collected.** Running the study requires ethics approval and participants. We provide the complete protocol (`docs/user_study/`) and the instrumented apparatus. All human-factors results in the paper come from a parametric simulation and are labelled as such.
* **No new live LLM runs.** No API budget or GPU was available, so the evaluation replays recorded trajectories. Counterfactual agent behaviour after a blocked call (for example, retries) is not observed. Sec. 7 of the paper discusses this limitation.
