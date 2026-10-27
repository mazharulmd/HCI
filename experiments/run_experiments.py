"""
Rigorous Experimental Evaluation & Statistical Hypothesis Testing Pipeline for PROV-Guard.

Executes a full-factorial evaluation across:
- 9 Defense Conditions (4 Baselines + 4 Ablation Conditions + 1 Full PROV-Guard Suite):
  1. B0_NO_DEFENSE: Autonomous execution without intervention
  2. B1_SPOTLIGHTING_SYSTEM: Delimiter / Spotlighting system-only guard (Hines et al., 2024)
  3. B2_STATIC_BANNER: Always-visible static telemetry warning banner
  4. B3_BINARY_MODAL: Uniform binary confirmation modal (Magentic-UI Action Guard / MCP default)
  5. ABL_NO_DLPA: PROV-Guard without Dual-Lineage Provenance Attribution
  6. ABL_NO_CGASD: PROV-Guard without Contextual Goal-Alignment & Semantic Drift
  7. ABL_NO_AFTCG: PROV-Guard without Adaptive Friction & Tiered Capability Gates (uniform interruption)
  8. ABL_NO_ICSP: PROV-Guard without Interactive Counterfactual & Sandbox Preview
  9. PROV_GUARD_FULL: Complete 4-pattern PROV-Guard HCI Defense Framework

- 48 Simulated Participants (stratified across Novice, Intermediate, and Security-Aware profiles)
- 250 Benchmark Scenarios per condition (100 Benign + 150 Malicious across 5 domains & 5 attack families)
  Total simulated trials: 9 conditions x 48 participants x 250 scenarios = 108,000 trials.

Computes:
- Attack Success Rate (ASR %) & Defense Effectiveness (DE %)
- False Positive Rate / Benign Task Interruption & Rejection (FPR %)
- Benign Task Completion Utility (Utility %)
- Signal Detection Theory metrics: Sensitivity (d'), Response Bias (c), F1-Score (%)
- User Workload (Simulated NASA-TLX 0-100), Habituation Index H(T), Decision Latency (s), Runtime Overhead (ms)
- Non-parametric & parametric statistical tests: Kruskal-Wallis H, Mann-Whitney U with Holm-Bonferroni
  step-down p-value correction, Cohen's d, and Cliff's delta effect sizes.
"""

import csv
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from hci_sec.models import AttackCategory, UserDecisionOutcome
from hci_sec.risk_gate import PROVGuardEngine, DefenseConfig
from hci_sec.user_model import CognitiveUserSimulator, UserProfile
from benchmarks.benchmark_suite import build_benchmark_scenarios


DEFENSE_CONDITIONS: List[Tuple[str, str, DefenseConfig]] = [
    (
        "B0_NO_DEFENSE",
        "No Defense (Autonomous)",
        DefenseConfig(mode="B0_NO_DEFENSE", enable_dlpa=False, enable_cgasd=False, enable_aftcg=False, enable_icsp=False),
    ),
    (
        "B1_SPOTLIGHTING_SYSTEM",
        "Spotlighting / Delimiter Guard",
        DefenseConfig(mode="B1_SPOTLIGHTING_SYSTEM", enable_dlpa=False, enable_cgasd=False, enable_aftcg=False, enable_icsp=False),
    ),
    (
        "B2_STATIC_BANNER",
        "Static Telemetry Banner",
        DefenseConfig(mode="B2_STATIC_BANNER", enable_dlpa=False, enable_cgasd=False, enable_aftcg=False, enable_icsp=False),
    ),
    (
        "B3_BINARY_MODAL",
        "Uniform Binary Action Modal",
        DefenseConfig(mode="B3_BINARY_MODAL", enable_dlpa=False, enable_cgasd=False, enable_aftcg=False, enable_icsp=False),
    ),
    (
        "ABL_NO_DLPA",
        "PROV-Guard w/o Provenance (No DLPA)",
        DefenseConfig(mode="ABL_NO_DLPA", enable_dlpa=False, enable_cgasd=True, enable_aftcg=True, enable_icsp=True),
    ),
    (
        "ABL_NO_CGASD",
        "PROV-Guard w/o Semantic Drift (No CGASD)",
        DefenseConfig(mode="ABL_NO_CGASD", enable_dlpa=True, enable_cgasd=False, enable_aftcg=True, enable_icsp=True),
    ),
    (
        "ABL_NO_AFTCG",
        "PROV-Guard w/o Adaptive Friction (No AFTCG)",
        DefenseConfig(mode="ABL_NO_AFTCG", enable_dlpa=True, enable_cgasd=True, enable_aftcg=False, enable_icsp=True),
    ),
    (
        "ABL_NO_ICSP",
        "PROV-Guard w/o Sandbox Preview (No ICSP)",
        DefenseConfig(mode="ABL_NO_ICSP", enable_dlpa=True, enable_cgasd=True, enable_aftcg=True, enable_icsp=False),
    ),
    (
        "PROV_GUARD_FULL",
        "PROV-Guard (Full 4-Pattern Suite)",
        DefenseConfig(mode="PROV_GUARD_FULL", enable_dlpa=True, enable_cgasd=True, enable_aftcg=True, enable_icsp=True),
    ),
]


def compute_sdt_metrics(tp: int, fn: int, fp: int, tn: int) -> Tuple[float, float, float]:
    """
    Compute Signal Detection Theory sensitivity (d'), response criterion bias (c),
    and F1-score for identifying and blocking malicious tool calls.
    Uses log-linear Hautus (1995) correction (+0.5 / +1.0) to avoid infinite z-scores.
    """
    hit_rate = (tp + 0.5) / (tp + fn + 1.0)
    fa_rate = (fp + 0.5) / (fp + tn + 1.0)

    z_hit = float(stats.norm.ppf(hit_rate))
    z_fa = float(stats.norm.ppf(fa_rate))

    d_prime = z_hit - z_fa
    criterion_c = -0.5 * (z_hit + z_fa)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) * 100.0 if (precision + recall) > 0 else 0.0
    return round(d_prime, 3), round(criterion_c, 3), round(f1, 2)


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Compute pooled Cohen's d effect size between two participant-level arrays."""
    nx, ny = len(x), len(y)
    dof = nx + ny - 2
    pool_sd = math.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / max(1, dof))
    if pool_sd < 1e-9:
        return 0.0
    return round(float((np.mean(x) - np.mean(y)) / pool_sd), 3)


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    """Compute non-parametric Cliff's delta effect size in [-1, 1]."""
    n_x, n_y = len(x), len(y)
    greater = 0
    less = 0
    for xi in x:
        for yj in y:
            if xi > yj:
                greater += 1
            elif xi < yj:
                less += 1
    return round((greater - less) / float(n_x * n_y), 3)


def holm_bonferroni(p_values: List[float]) -> List[float]:
    """Apply Holm-Bonferroni step-down multiple-comparison correction."""
    m = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, pval) in enumerate(indexed):
        adj = min(1.0, pval * (m - rank))
        running_max = max(running_max, adj)
        corrected[orig_idx] = running_max
    return corrected


def run_all_experiments() -> Dict[str, Any]:
    scenarios = build_benchmark_scenarios()
    cohort: List[UserProfile] = CognitiveUserSimulator.generate_cohort(n_participants=48, base_seed=2026)

    condition_summaries: Dict[str, Any] = {}
    participant_level_records: List[Dict[str, Any]] = []
    habituation_trajectories: Dict[str, List[float]] = {}
    attack_category_breakdown: Dict[str, Dict[str, float]] = {}
    domain_breakdown: Dict[str, Dict[str, float]] = {}

    for cond_idx, (cond_code, cond_label, config) in enumerate(DEFENSE_CONDITIONS):
        engine = PROVGuardEngine(config)

        # Pre-evaluate deterministic risk & UI for all 250 scenarios under this condition
        precomputed = [engine.assess_proposal(sc) for sc in scenarios]
        avg_engine_latency_ms = float(np.mean([r[0].analysis_latency_ms for r in precomputed]))

        # Track per-participant metrics for statistical testing
        part_asr: List[float] = []
        part_de: List[float] = []
        part_fpr: List[float] = []
        part_util: List[float] = []
        part_dprime: List[float] = []
        part_bias_c: List[float] = []
        part_f1: List[float] = []
        part_tlx: List[float] = []
        part_rt: List[float] = []
        part_interrupt_rate: List[float] = []
        part_final_hab: List[float] = []

        # Track trial-by-trial average habituation across participants (250 trials)
        trial_hab_sum = np.zeros(len(scenarios), dtype=float)
        trial_asr_rolling = np.zeros(len(scenarios), dtype=float)

        # Attack category & domain accumulators
        cat_hits: Dict[str, List[int]] = {cat.value: [0, 0] for cat in AttackCategory if cat != AttackCategory.BENIGN}
        dom_hits: Dict[str, List[int]] = {d: [0, 0] for d in ("email_workspace", "cloud_drive", "banking_finance", "code_ide", "calendar_sched")}

        for p_idx, profile in enumerate(cohort):
            sim = CognitiveUserSimulator(profile, seed=10000 + cond_idx * 500 + p_idx)
            sim.reset_session()

            tp = fn = fp = tn = 0
            interrupted_count = 0
            tlx_vals: List[float] = []
            rt_vals: List[float] = []

            for t_idx, (sc, (assessment, ui)) in enumerate(zip(scenarios, precomputed)):
                outcome: UserDecisionOutcome = sim.evaluate_trial(t_idx, sc, assessment, ui)
                trial_hab_sum[t_idx] += outcome.habituation_level
                if sc.is_malicious_ground_truth and outcome.attack_succeeded:
                    trial_asr_rolling[t_idx] += 1.0

                if outcome.ui_interrupted_user:
                    interrupted_count += 1
                tlx_vals.append(outcome.nasa_tlx_workload)
                rt_vals.append(outcome.decision_time_sec)

                if sc.is_malicious_ground_truth:
                    cat_hits[sc.attack_category.value][1] += 1
                    dom_hits[sc.domain][1] += 1
                    if outcome.attack_succeeded:
                        fn += 1  # Attack succeeded = missed detection
                        cat_hits[sc.attack_category.value][0] += 1
                        dom_hits[sc.domain][0] += 1
                    else:
                        tp += 1  # Attack prevented = true positive block
                else:
                    if outcome.false_positive_block:
                        fp += 1
                    else:
                        tn += 1

            asr = (fn / float(tp + fn)) * 100.0
            de = (tp / float(tp + fn)) * 100.0
            fpr = (fp / float(fp + tn)) * 100.0
            util = (tn / float(fp + tn)) * 100.0
            d_prime, crit_c, f1_val = compute_sdt_metrics(tp, fn, fp, tn)
            mean_tlx = float(np.mean(tlx_vals))
            mean_rt = float(np.mean(rt_vals))
            int_rate = (interrupted_count / float(len(scenarios))) * 100.0
            final_hab = sim.effective_habituation

            part_asr.append(asr)
            part_de.append(de)
            part_fpr.append(fpr)
            part_util.append(util)
            part_dprime.append(d_prime)
            part_bias_c.append(crit_c)
            part_f1.append(f1_val)
            part_tlx.append(mean_tlx)
            part_rt.append(mean_rt)
            part_interrupt_rate.append(int_rate)
            part_final_hab.append(final_hab)

            participant_level_records.append({
                "condition_code": cond_code,
                "condition_label": cond_label,
                "participant_id": profile.participant_id,
                "expertise_level": profile.expertise_level,
                "asr_pct": round(asr, 3),
                "defense_effectiveness_pct": round(de, 3),
                "fpr_pct": round(fpr, 3),
                "benign_utility_pct": round(util, 3),
                "d_prime": d_prime,
                "criterion_c": crit_c,
                "f1_pct": f1_val,
                "nasa_tlx": round(mean_tlx, 2),
                "decision_time_s": round(mean_rt, 3),
                "interruption_rate_pct": round(int_rate, 2),
                "final_habituation": round(final_hab, 4),
            })

        habituation_trajectories[cond_code] = [round(float(x / len(cohort)), 4) for x in trial_hab_sum]

        attack_category_breakdown[cond_code] = {
            cat_k: round((succ / float(tot)) * 100.0, 2) if tot > 0 else 0.0
            for cat_k, (succ, tot) in cat_hits.items()
        }
        domain_breakdown[cond_code] = {
            dom_k: round((succ / float(tot)) * 100.0, 2) if tot > 0 else 0.0
            for dom_k, (succ, tot) in dom_hits.items()
        }

        condition_summaries[cond_code] = {
            "code": cond_code,
            "label": cond_label,
            "n_participants": len(cohort),
            "n_scenarios": len(scenarios),
            "asr_mean": round(float(np.mean(part_asr)), 2),
            "asr_sd": round(float(np.std(part_asr, ddof=1)), 2),
            "de_mean": round(float(np.mean(part_de)), 2),
            "de_sd": round(float(np.std(part_de, ddof=1)), 2),
            "fpr_mean": round(float(np.mean(part_fpr)), 2),
            "fpr_sd": round(float(np.std(part_fpr, ddof=1)), 2),
            "utility_mean": round(float(np.mean(part_util)), 2),
            "utility_sd": round(float(np.std(part_util, ddof=1)), 2),
            "d_prime_mean": round(float(np.mean(part_dprime)), 2),
            "d_prime_sd": round(float(np.std(part_dprime, ddof=1)), 2),
            "criterion_c_mean": round(float(np.mean(part_bias_c)), 2),
            "f1_mean": round(float(np.mean(part_f1)), 2),
            "f1_sd": round(float(np.std(part_f1, ddof=1)), 2),
            "nasa_tlx_mean": round(float(np.mean(part_tlx)), 2),
            "nasa_tlx_sd": round(float(np.std(part_tlx, ddof=1)), 2),
            "decision_time_s_mean": round(float(np.mean(part_rt)), 2),
            "decision_time_s_sd": round(float(np.std(part_rt, ddof=1)), 2),
            "interruption_rate_pct": round(float(np.mean(part_interrupt_rate)), 2),
            "final_habituation_mean": round(float(np.mean(part_final_hab)), 3),
            "engine_latency_ms": round(avg_engine_latency_ms, 3),
            "_raw_asr": part_asr,
            "_raw_dprime": part_dprime,
            "_raw_tlx": part_tlx,
            "_raw_fpr": part_fpr,
            "_raw_hab": part_final_hab,
        }

    # Perform Statistical Significance Tests comparing PROV_GUARD_FULL against all baselines & ablations
    full_stats = condition_summaries["PROV_GUARD_FULL"]
    comparisons = [
        c_code for c_code, _, _ in DEFENSE_CONDITIONS if c_code != "PROV_GUARD_FULL"
    ]

    raw_p_asr: List[float] = []
    raw_p_dprime: List[float] = []
    raw_p_tlx: List[float] = []
    stat_rows: List[Dict[str, Any]] = []

    for comp_code in comparisons:
        comp = condition_summaries[comp_code]
        x_asr = np.array(full_stats["_raw_asr"])
        y_asr = np.array(comp["_raw_asr"])
        u_asr, p_asr = stats.mannwhitneyu(x_asr, y_asr, alternative="two-sided")

        x_dp = np.array(full_stats["_raw_dprime"])
        y_dp = np.array(comp["_raw_dprime"])
        u_dp, p_dp = stats.mannwhitneyu(x_dp, y_dp, alternative="two-sided")

        x_tlx = np.array(full_stats["_raw_tlx"])
        y_tlx = np.array(comp["_raw_tlx"])
        u_tlx, p_tlx = stats.mannwhitneyu(x_tlx, y_tlx, alternative="two-sided")

        raw_p_asr.append(float(p_asr))
        raw_p_dprime.append(float(p_dp))
        raw_p_tlx.append(float(p_tlx))

        stat_rows.append({
            "comparison": f"PROV_GUARD_FULL vs. {comp_code}",
            "comparator_label": comp["label"],
            "delta_asr_pct": round(full_stats["asr_mean"] - comp["asr_mean"], 2),
            "asr_u_stat": float(u_asr),
            "asr_p_raw": float(p_asr),
            "asr_cohens_d": cohens_d(x_asr, y_asr),
            "asr_cliffs_delta": cliffs_delta(x_asr, y_asr),
            "delta_dprime": round(full_stats["d_prime_mean"] - comp["d_prime_mean"], 2),
            "dprime_p_raw": float(p_dp),
            "dprime_cohens_d": cohens_d(x_dp, y_dp),
            "delta_tlx": round(full_stats["nasa_tlx_mean"] - comp["nasa_tlx_mean"], 2),
            "tlx_p_raw": float(p_tlx),
            "tlx_cohens_d": cohens_d(x_tlx, y_tlx),
        })

    adj_p_asr = holm_bonferroni(raw_p_asr)
    adj_p_dp = holm_bonferroni(raw_p_dprime)
    adj_p_tlx = holm_bonferroni(raw_p_tlx)

    for idx, row in enumerate(stat_rows):
        row["asr_p_holm"] = adj_p_asr[idx]
        row["dprime_p_holm"] = adj_p_dp[idx]
        row["tlx_p_holm"] = adj_p_tlx[idx]

    # Omnibus Kruskal-Wallis across interactive conditions
    interactive_codes = ["B2_STATIC_BANNER", "B3_BINARY_MODAL", "ABL_NO_DLPA", "ABL_NO_CGASD", "ABL_NO_AFTCG", "ABL_NO_ICSP", "PROV_GUARD_FULL"]
    kw_asr_stat, kw_asr_p = stats.kruskal(*[condition_summaries[c]["_raw_asr"] for c in interactive_codes])
    kw_dp_stat, kw_dp_p = stats.kruskal(*[condition_summaries[c]["_raw_dprime"] for c in interactive_codes])
    kw_tlx_stat, kw_tlx_p = stats.kruskal(*[condition_summaries[c]["_raw_tlx"] for c in interactive_codes])

    # Expertise-stratified performance under PROV_GUARD_FULL vs B3_BINARY_MODAL
    expertise_summary: Dict[str, Any] = {}
    for mode_key in ("B3_BINARY_MODAL", "PROV_GUARD_FULL"):
        expertise_summary[mode_key] = {}
        for exp_level in ("novice", "intermediate", "security_aware"):
            sub = [
                r for r in participant_level_records
                if r["condition_code"] == mode_key and r["expertise_level"] == exp_level
            ]
            expertise_summary[mode_key][exp_level] = {
                "asr_mean": round(float(np.mean([r["asr_pct"] for r in sub])), 2),
                "d_prime_mean": round(float(np.mean([r["d_prime"] for r in sub])), 2),
                "nasa_tlx_mean": round(float(np.mean([r["nasa_tlx"] for r in sub])), 2),
                "fpr_mean": round(float(np.mean([r["fpr_pct"] for r in sub])), 2),
            }

    # Remove raw arrays before JSON serialization
    clean_summaries = {}
    for k, v in condition_summaries.items():
        clean_summaries[k] = {ck: cv for ck, cv in v.items() if not ck.startswith("_raw_")}

    results_bundle = {
        "experiment_metadata": {
            "total_conditions": len(DEFENSE_CONDITIONS),
            "n_participants": len(cohort),
            "n_scenarios_per_condition": len(scenarios),
            "n_benign_scenarios": 100,
            "n_malicious_scenarios": 150,
            "total_simulated_trials": len(DEFENSE_CONDITIONS) * len(cohort) * len(scenarios),
            "omnibus_kruskal_wallis": {
                "asr_H": round(float(kw_asr_stat), 3),
                "asr_p": float(kw_asr_p),
                "dprime_H": round(float(kw_dp_stat), 3),
                "dprime_p": float(kw_dp_p),
                "tlx_H": round(float(kw_tlx_stat), 3),
                "tlx_p": float(kw_tlx_p),
            },
        },
        "condition_summaries": clean_summaries,
        "attack_category_asr_pct": attack_category_breakdown,
        "domain_asr_pct": domain_breakdown,
        "statistical_comparisons": stat_rows,
        "expertise_stratification": expertise_summary,
        "habituation_trajectories": habituation_trajectories,
    }

    out_dir = ROOT / "experiments" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experimental_results.json").write_text(
        json.dumps(results_bundle, indent=2), encoding="utf-8"
    )

    # Save participant-level CSV
    csv_path = out_dir / "participant_level_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(participant_level_records[0].keys()))
        writer.writeheader()
        writer.writerows(participant_level_records)

    return results_bundle


if __name__ == "__main__":
    bundle = run_all_experiments()
    print("=== EXPERIMENTAL SUMMARY (N=48 participants x 250 scenarios = 12,000 trials/condition) ===")
    header = f"{'Condition':<26} | {'ASR (%)':>9} | {'DefEff(%)':>9} | {'FPR (%)':>8} | {'d-prime':>8} | {'F1 (%)':>8} | {'TLX':>7} | {'RT(s)':>6} | {'Int(%)':>6}"
    print(header)
    print("-" * len(header))
    for code, s in bundle["condition_summaries"].items():
        print(
            f"{code:<26} | {s['asr_mean']:>5.2f}±{s['asr_sd']:<3.1f} | "
            f"{s['de_mean']:>5.2f}±{s['de_sd']:<3.1f} | {s['fpr_mean']:>5.2f}±{s['fpr_sd']:<2.1f} | "
            f"{s['d_prime_mean']:>5.2f}   | {s['f1_mean']:>6.2f}  | {s['nasa_tlx_mean']:>6.1f} | "
            f"{s['decision_time_s_mean']:>5.2f} | {s['interruption_rate_pct']:>5.1f}"
        )
