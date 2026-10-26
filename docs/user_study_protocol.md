# Proposed user-study protocol (ethics review required)

**Status:** protocol draft only. No ethics/IRB approval has been obtained; no participants have been recruited, and no human-subject data exists. Do not recruit or run this study before local institutional review and approval.

## Design

Within-subject, counterbalanced interface study with four UI conditions: (A) proposed action only, (B) action plus risk rationale, (C) action plus source provenance and permission scope, (D) combined source-to-action review and explicit confirmation. Use matched benign and malicious scenarios with multiple surface forms. Participants should not see scenario ground-truth labels. Every tool action is simulated and has no external side effect.

## Participants and safeguards

Recruit adults (18+) who use web, email, or productivity software, with a range of AI-agent familiarity. A power analysis based on a separate pilot should set the sample size. Participation is voluntary, compensated consistently with local norms, and withdrawable without penalty. Collect only coarse demographics needed for analysis; avoid names, account identifiers, real prompts, and credentials. Store pseudonymous data encrypted with an access and retention plan approved by the institution. Use a debrief explaining prompt injection and the fact that all actions were simulated.

## Procedure

Consent → brief tutorial and comprehension check → randomized tasks across conditions → workload/trust questions after blocks → debrief. Use fictional organizations, people, and records. Include a safe practice trial. Provide a pause/withdraw option. Pilot accessibility, color contrast, keyboard operation, and assistive-technology support before recruitment.

## Outcomes and analysis

Record only condition, scenario ID, approve/reject choice, correctness label, response time, and optional confidence. Collect NASA-TLX after each block. Pre-register mixed-effects analyses with participant and scenario random intercepts; report effect sizes and confidence intervals, and correct planned pairwise comparisons. Treat failure to detect a difference as inconclusive unless the design is powered for equivalence. Exclude participants only using pre-registered criteria such as failed comprehension checks or incomplete sessions.

## Risks and ethics

The main risks are mild frustration, exposure to adversarial text, and possible overconfidence in interface warnings. Limit attack text to fictional, non-graphic content; provide debrief and contact information for the research team and ethics office. Explain that the prototype is not a real security product. Approval, consent materials, compensation, data handling, and recruitment language require institutional review before study execution.
