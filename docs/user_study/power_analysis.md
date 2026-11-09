# Power analysis for the lab study

**Status:** done before recruitment, with **simulated** studies only. No participant data exist.

* Script: `experiments/power_user_study.py`
* Results: `results/power/`
* Settings: `results/power/power_settings*.json`

## Method

Each simulated study is analysed with the pre-registered primary analysis itself:
`gee_main_effects` in `experiments/analyze_user_study.py`, a logistic GEE clustered by
participant, with scenario as a fixed effect and Holm correction over the two main
effects. **Power** is the share of 400 simulated studies per setting in which an effect
has a Holm-adjusted p < .05. Fits that fail count as misses; none failed. A calibration
test (`tests/test_user_study.py`) checks that the procedure rarely rejects when there is
no effect, and almost always rejects when the effect is large.

**n** below is the number of *analysed* participants per condition (cell). Recruit about
10% more to allow for exclusions. The current plan, 55 recruited per cell, gives about
50 analysed.

Two ways of generating data:

1. **Assumption grid (model-free).** Each participant's chance of stopping an attack
   follows a logistic model. It includes a baseline prevention rate for confirm-all (B)
   at three values: 0.3, 0.5 and 0.7. Both main effects have the same odds ratio: 1.5,
   2.0 or 2.5. Participants differ by a random effect with SD σ_u = 0.5, 1.0 or 1.5 on the
   logit scale (intraclass correlations of about 0.07, 0.23 and 0.41). Scenarios differ
   by SD 0.5.
2. **Model-anchored (simulation, not human data).** Participants are drawn from the
   paper's simulated-user model (signal detection with habituation; novice, intermediate
   and security-aware strata). They work through the real study sequence: two practice
   tasks, then the 16 tasks, with each condition's real dialog schedule. This shows what
   the paper's own hypotheses imply for power, nothing more.

## Results

### 1. Assumption grid: power to detect *both* main effects

The tables give the probability that both main effects are significant. Power for a
single effect is higher (see `power_grid.csv`).

#### Odds ratio 1.5

| baseline_B | sigma_u | n = 30 | n = 40 | n = 50 | n = 60 | n = 80 | n = 100 | n = 150 |
|---|---|---|---|---|---|---|---|---|
| 0.3 | 0.5 | 0.21 | 0.33 | 0.42 | 0.57 | 0.77 | 0.86 | 0.96 |
| 0.3 | 1.0 | 0.10 | 0.17 | 0.21 | 0.30 | 0.42 | 0.54 | 0.82 |
| 0.3 | 1.5 | 0.06 | 0.09 | 0.08 | 0.14 | 0.21 | 0.28 | 0.52 |
| 0.5 | 0.5 | 0.24 | 0.34 | 0.46 | 0.58 | 0.70 | 0.82 | 0.98 |
| 0.5 | 1.0 | 0.10 | 0.14 | 0.23 | 0.29 | 0.46 | 0.57 | 0.83 |
| 0.5 | 1.5 | 0.05 | 0.07 | 0.08 | 0.10 | 0.15 | 0.28 | 0.49 |
| 0.7 | 0.5 | 0.14 | 0.22 | 0.34 | 0.44 | 0.61 | 0.72 | 0.90 |
| 0.7 | 1.0 | 0.07 | 0.10 | 0.16 | 0.22 | 0.35 | 0.49 | 0.73 |
| 0.7 | 1.5 | 0.03 | 0.04 | 0.10 | 0.10 | 0.18 | 0.23 | 0.45 |

#### Odds ratio 2.0

| baseline_B | sigma_u | n = 30 | n = 40 | n = 50 | n = 60 | n = 80 | n = 100 | n = 150 |
|---|---|---|---|---|---|---|---|---|
| 0.3 | 0.5 | 0.83 | 0.93 | 0.98 | 0.98 | 1.00 | 1.00 | 1.00 |
| 0.3 | 1.0 | 0.50 | 0.70 | 0.81 | 0.88 | 0.97 | 0.97 | 1.00 |
| 0.3 | 1.5 | 0.28 | 0.37 | 0.50 | 0.61 | 0.76 | 0.90 | 0.98 |
| 0.5 | 0.5 | 0.74 | 0.90 | 0.96 | 0.98 | 0.99 | 1.00 | 1.00 |
| 0.5 | 1.0 | 0.46 | 0.58 | 0.80 | 0.86 | 0.95 | 0.98 | 1.00 |
| 0.5 | 1.5 | 0.23 | 0.34 | 0.46 | 0.59 | 0.74 | 0.86 | 0.97 |
| 0.7 | 0.5 | 0.62 | 0.77 | 0.85 | 0.91 | 0.98 | 0.99 | 1.00 |
| 0.7 | 1.0 | 0.37 | 0.50 | 0.67 | 0.75 | 0.93 | 0.97 | 1.00 |
| 0.7 | 1.5 | 0.19 | 0.31 | 0.40 | 0.51 | 0.70 | 0.80 | 0.96 |

#### Odds ratio 2.5

| baseline_B | sigma_u | n = 30 | n = 40 | n = 50 | n = 60 | n = 80 | n = 100 | n = 150 |
|---|---|---|---|---|---|---|---|---|
| 0.3 | 0.5 | 0.99 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.3 | 1.0 | 0.76 | 0.95 | 0.98 | 0.99 | 1.00 | 1.00 | 1.00 |
| 0.3 | 1.5 | 0.50 | 0.70 | 0.86 | 0.90 | 0.96 | 0.99 | 1.00 |
| 0.5 | 0.5 | 0.94 | 0.98 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| 0.5 | 1.0 | 0.75 | 0.91 | 0.97 | 0.99 | 1.00 | 1.00 | 1.00 |
| 0.5 | 1.5 | 0.52 | 0.67 | 0.82 | 0.84 | 0.96 | 0.99 | 1.00 |
| 0.7 | 0.5 | 0.80 | 0.91 | 0.98 | 0.98 | 1.00 | 1.00 | 1.00 |
| 0.7 | 1.0 | 0.68 | 0.81 | 0.91 | 0.95 | 0.98 | 1.00 | 1.00 |
| 0.7 | 1.5 | 0.41 | 0.58 | 0.73 | 0.81 | 0.93 | 0.98 | 1.00 |

`power_recommendation.csv` lists, for every setting, the smallest n that reaches 80%
power for both effects, and the number to recruit.

**Reading:** with about 50 analysed per cell, the design detects both effects with at
least 80% power only if each effect is at least an odds ratio of about 2 **and**
participants are not very heterogeneous (σ_u ≤ 1). Effects of odds ratio 1.5 need
100–150 or more per cell.

### 2. Model-anchored: what the paper's own user model implies (simulation)

Mean prevention of the four attacks, balanced population, 16-task design:

| Condition | Prevention |
|---|---|
| B confirm-all | 0.45 |
| C selectivity only | 0.49 |
| D evidence only | 0.81 |
| A full CLEAR | 0.83 |

* **Evidence (H-U2):** implied odds ratio of about 5.4. Power is 1.00 at every n tested
  (30–150 per cell), in both populations.
* **Selectivity (H-U1):** implied odds ratio of about 1.15–1.2. Power:

| population | n = 30 | n = 40 | n = 50 | n = 60 | n = 80 | n = 100 | n = 150 |
|---|---|---|---|---|---|---|---|
| balanced | 0.10 | 0.14 | 0.16 | 0.14 | 0.20 | 0.24 | 0.31 |
| mostly novice | 0.14 | 0.13 | 0.18 | 0.24 | 0.25 | 0.29 | 0.46 |

**Why selectivity is weak in this design.** Its benefit works through habituation,
because fewer dialogs mean less rubber-stamping. In the 16 study tasks, CLEAR raises 13
dialogs and confirm-all 18. Of the 12 benign tasks, 4 need no CLEAR dialog. On the
held-out benchmark, 43% of benign tasks with a side-effecting action need none, and
CLEAR asks 0.84 vs 1.72 questions per such task (51% fewer).

**Design variants** (balanced population; power for selectivity):

| benign tasks | tasks per session | n = 50 | n = 100 | n = 150 |
|---|---|---|---|---|
| study set (current) | 16 | 0.13 | 0.21 | 0.32 |
| study set | 32 | 0.19 | 0.27 | 0.39 |
| study set | 48 | 0.18 | 0.26 | 0.34 |
| representative of the benchmark | 16 | 0.20 | 0.43 | 0.56 |
| representative of the benchmark | 32 | 0.29 | 0.50 | 0.67 |
| representative of the benchmark | 48 | 0.30 | 0.47 | 0.61 |

A representative task set helps more than a longer session. Even so, under this model
no feasible design reaches 80% power for selectivity *on the prevention outcome*: the
model predicts a gain of 4–6 percentage points.

## Conclusions for the protocol

1. **N = 220 (55 per cell) is adequate for the evidence effect (H-U2)** under the
   paper's model. It is also adequate for any main effect of odds ratio 2 or more with
   moderate heterogeneity (σ_u ≤ 1).
2. **The selectivity effect on prevention (H-U1) is not adequately powered** at N = 220
   if the paper's model is right, and no feasible sample size or session length fixes
   that. Under the model, selectivity mainly reduces *burden* (fewer dialogs, less
   workload) while keeping prevention. That is a different, testable claim.
3. **A decision is needed before preregistration.** Options:
   * **(a)** Keep H-U1 as confirmatory and accept low power. Not recommended: a null
     result would be uninformative.
   * **(b)** Demote H-U1 to exploratory. Make H-U2 (evidence) the primary confirmatory
     hypothesis, keep H-U3 (non-inferiority of burden and completion), and add a
     non-inferiority test that selectivity does not reduce prevention.
   * **(c)** Rebuild the benign task set to match the benchmark's escalation
     distribution (more tasks that CLEAR does not escalate) and increase N. This
     improves the test of selectivity but still falls short of 80% under the model.
4. **After the pilot sessions**, re-run the grid with the observed prevention rate in
   confirm-all and an estimate of σ_u, for example:
   `python experiments/power_user_study.py --baseline 0.45 --sigma-u 1.2 --skip-model`.
