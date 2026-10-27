"""
Publication-Quality Figure Generator for the PROV-Guard Q1 Manuscript & Repository.
Generates 5 high-resolution figures (300 DPI PNG + vector PDF) with zero label collisions:
- fig1_asr_fpr_comparison: Main comparative results across all 9 defense conditions
- fig2_attack_taxonomy_heatmap: Attack Success Rate (%) across 5 attack families x 9 conditions
- fig3_habituation_trajectories: Longitudinal habituation dynamics across 250 agent interactions
- fig4_pareto_security_workload: Security (Defense Effectiveness %) vs. Cognitive Workload (NASA-TLX) & d'
- fig5_expertise_stratification: Novice vs. Intermediate vs. Security-Aware operator performance
"""

import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PRIMARY_NAVY = "#1B365D"
TEAL_ACCENT = "#008080"
CORAL_WARN = "#D9534F"
AMBER_MID = "#E67E22"
SLATE_GRAY = "#5D6D7E"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 10,
    "axes.titlesize": 11.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.labelweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.8,
    "figure.dpi": 300,
})


def generate_all_figures(results_json_path: Path, output_dirs: list[Path]) -> None:
    data = json.loads(results_json_path.read_text(encoding="utf-8"))
    summaries = data["condition_summaries"]
    atk_matrix = data["attack_category_asr_pct"]
    hab_traj = data["habituation_trajectories"]
    expertise = data["expertise_stratification"]

    for d in output_dirs:
        d.mkdir(parents=True, exist_ok=True)

    def _save(fig, name: str):
        for d in output_dirs:
            fig.savefig(d / f"{name}.png", dpi=300, bbox_inches="tight")
            fig.savefig(d / f"{name}.pdf", bbox_inches="tight")
        plt.close(fig)

    # -------------------------------------------------------------------------
    # FIGURE 1: Comparative ASR (%) and False Positive Rate (%) across 9 Conditions
    # -------------------------------------------------------------------------
    cond_order = [
        "B0_NO_DEFENSE",
        "B1_SPOTLIGHTING_SYSTEM",
        "B2_STATIC_BANNER",
        "B3_BINARY_MODAL",
        "ABL_NO_AFTCG",
        "ABL_NO_DLPA",
        "ABL_NO_ICSP",
        "ABL_NO_CGASD",
        "PROV_GUARD_FULL",
    ]
    short_labels = [
        "B0: No Defense",
        "B1: Spotlighting",
        "B2: Static Banner",
        "B3: Binary Modal",
        "Abl: w/o AFTCG",
        "Abl: w/o DLPA",
        "Abl: w/o ICSP",
        "Abl: w/o CGASD",
        "PROV-Guard (Full)",
    ]

    asr_means = [summaries[c]["asr_mean"] for c in cond_order]
    asr_sds = [summaries[c]["asr_sd"] for c in cond_order]
    fpr_means = [summaries[c]["fpr_mean"] for c in cond_order]
    fpr_sds = [summaries[c]["fpr_sd"] for c in cond_order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.5), sharey=True)
    y_pos = np.arange(len(cond_order))

    colors_asr = [
        SLATE_GRAY if c.startswith("B") else (AMBER_MID if c.startswith("ABL") else TEAL_ACCENT)
        for c in cond_order
    ]

    bars1 = ax1.barh(y_pos, asr_means, xerr=asr_sds, height=0.62, color=colors_asr, edgecolor="#1E293B", linewidth=0.7, capsize=3)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(short_labels, fontweight="bold")
    ax1.invert_yaxis()
    ax1.set_xlabel("Attack Success Rate — ASR (%) [Lower is Better]")
    ax1.set_title("(a) Indirect Prompt Injection Attack Success Rate")
    ax1.set_xlim(0, 118)
    ax1.grid(axis="x", linestyle="--", alpha=0.4)
    for bar, val, sd in zip(bars1, asr_means, asr_sds):
        ax1.text(val + sd + 1.8, bar.get_y() + bar.get_height() / 2, f"{val:.1f}%", va="center", ha="left", fontsize=8.5, fontweight="bold")

    bars2 = ax2.barh(y_pos, fpr_means, xerr=fpr_sds, height=0.62, color=CORAL_WARN, alpha=0.85, edgecolor="#1E293B", linewidth=0.7, capsize=3)
    ax2.set_xlabel("Benign Task False Positive Rejection — FPR (%) [Lower is Better]")
    ax2.set_title("(b) Benign Workflow False Rejection Rate")
    ax2.set_xlim(0, 23.5)
    ax2.grid(axis="x", linestyle="--", alpha=0.4)
    for bar, val, sd in zip(bars2, fpr_means, fpr_sds):
        ax2.text(val + sd + 0.45, bar.get_y() + bar.get_height() / 2, f"{val:.2f}%", va="center", ha="left", fontsize=8.5, fontweight="bold")

    fig.tight_layout()
    _save(fig, "fig1_asr_fpr_comparison")

    # -------------------------------------------------------------------------
    # FIGURE 2: Attack Category Breakdown Heatmap (5 Attack Families x 9 Conditions)
    # -------------------------------------------------------------------------
    atk_keys = [
        "DIRECT_OVERRIDE",
        "CONTEXT_FRAMING",
        "OBFUSCATED_PAYLOAD",
        "CROSS_TOOL_CHAIN",
        "GOAL_MIMICRY",
    ]
    atk_labels = [
        "A1: Direct\nOverride",
        "A2: Context\nFraming",
        "A3: Obfuscated\nPayload",
        "A4: Cross-Tool\nChaining",
        "A5: Semantic\nGoal-Mimicry",
    ]

    matrix = np.array([[atk_matrix[c][ak] for ak in atk_keys] for c in cond_order])

    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(np.arange(len(atk_labels)))
    ax.set_xticklabels(atk_labels, fontweight="bold")
    ax.set_yticks(np.arange(len(short_labels)))
    ax.set_yticklabels(short_labels, fontweight="bold")
    ax.set_title("Attack Success Rate (%) by Injection Taxonomy and Defense Architecture")

    for i in range(len(short_labels)):
        for j in range(len(atk_labels)):
            val = matrix[i, j]
            txt_color = "white" if val > 55 else "#1E293B"
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center", color=txt_color, fontsize=8.5, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("Attack Success Rate — ASR (%)", fontweight="bold")
    fig.tight_layout()
    _save(fig, "fig2_attack_taxonomy_heatmap")

    # -------------------------------------------------------------------------
    # FIGURE 3: Longitudinal Warning Habituation Trajectories over 250 Trials
    # -------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.0, 4.3))
    trials = np.arange(1, 251)

    plot_specs = [
        ("B2_STATIC_BANNER", "B2: Static Warning Banner (100% Interrupt)", "#C0392B", "-", 2.0),
        ("B3_BINARY_MODAL", "B3: Uniform Binary Modal (80% Interrupt)", "#E67E22", "--", 2.0),
        ("ABL_NO_AFTCG", "Ablation: PROV-Guard w/o Adaptive Friction", "#8E44AD", "-.", 1.8),
        ("ABL_NO_DLPA", "Ablation: PROV-Guard w/o Provenance Attribution", "#2980B9", ":", 1.8),
        ("PROV_GUARD_FULL", "PROV-Guard Full (Risk-Calibrated + Constructive Reset)", TEAL_ACCENT, "-", 2.6),
    ]

    for code, lbl, col, ls, lw in plot_specs:
        y_vals = hab_traj[code]
        kernel = np.ones(5) / 5.0
        y_smooth = np.convolve(y_vals, kernel, mode="same")
        y_smooth[0:2] = y_vals[0:2]
        y_smooth[-2:] = y_vals[-2:]
        ax.plot(trials, y_smooth, label=lbl, color=col, linestyle=ls, linewidth=lw)

    ax.set_xlabel("Sequential AI Agent Tool-Use Trial Index (t = 1 ... 250)")
    ax.set_ylabel("Neuro-Behavioral Habituation Index H(t) [0–1]")
    ax.set_title("Longitudinal Warning Habituation Dynamics Across Multi-Step Agent Sessions")
    ax.set_xlim(1, 250)
    ax.set_ylim(0, 1.03)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="center right", frameon=True, facecolor="white", framealpha=0.94)
    fig.tight_layout()
    _save(fig, "fig3_habituation_trajectories")

    # -------------------------------------------------------------------------
    # FIGURE 4: Security-Usability Trade-off (Defense Effectiveness vs. NASA-TLX & d')
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.6))

    interactive_conds = [
        ("B1_SPOTLIGHTING_SYSTEM", "B1: Spotlighting", SLATE_GRAY, "s", (8, 6)),
        ("B2_STATIC_BANNER", "B2: Static Banner", CORAL_WARN, "v", (-12, 8)),
        ("B3_BINARY_MODAL", "B3: Binary Modal", "#C0392B", "^", (-14, -14)),
        ("ABL_NO_DLPA", "w/o DLPA", AMBER_MID, "o", (-34, 6)),
        ("ABL_NO_AFTCG", "w/o AFTCG", "#8E44AD", "D", (34, -8)),
        ("ABL_NO_ICSP", "w/o ICSP", "#2980B9", "P", (32, -6)),
        ("ABL_NO_CGASD", "w/o CGASD", "#27AE60", "X", (-34, 6)),
        ("PROV_GUARD_FULL", "PROV-Guard (Full)", TEAL_ACCENT, "*", (0, -16)),
    ]

    for code, lbl, col, mk, (dx, dy) in interactive_conds:
        s = summaries[code]
        sz = 190 if code == "PROV_GUARD_FULL" else 95
        ax1.scatter(s["nasa_tlx_mean"], s["de_mean"], color=col, marker=mk, s=sz, edgecolors="#1E293B", linewidth=0.8, label=lbl, zorder=4)
        ax1.annotate(
            lbl,
            (s["nasa_tlx_mean"], s["de_mean"]),
            xytext=(dx, dy),
            textcoords="offset points",
            ha="center",
            fontsize=8.2,
            fontweight="bold",
            arrowprops=dict(arrowstyle="-", color="#64748B", lw=0.6) if abs(dx) > 20 else None,
        )

    ax1.set_xlabel("Subjective Cognitive Workload — NASA-TLX (0–100) [Lower is Better]")
    ax1.set_ylabel("Defense Effectiveness — DE (%) [Higher is Better]")
    ax1.set_title("(a) Security vs. Cognitive Workload Pareto Frontier")
    ax1.set_xlim(4, 78)
    ax1.set_ylim(-2, 108)
    ax1.grid(True, linestyle="--", alpha=0.4)

    # Panel (b): Signal Detection Sensitivity d' across conditions
    dp_codes = [c[0] for c in interactive_conds]
    dp_labels = [c[1] for c in interactive_conds]
    dp_vals = [summaries[c]["d_prime_mean"] for c in dp_codes]
    dp_sds = [summaries[c]["d_prime_sd"] for c in dp_codes]
    dp_cols = [c[2] for c in interactive_conds]

    x_idx = np.arange(len(dp_codes))
    bars_dp = ax2.bar(x_idx, dp_vals, yerr=dp_sds, width=0.56, color=dp_cols, edgecolor="#1E293B", linewidth=0.7, capsize=3)
    ax2.axhline(0.0, color="#1E293B", linewidth=0.8, linestyle="-")
    ax2.set_xticks(x_idx)
    ax2.set_xticklabels(dp_labels, rotation=26, ha="right", fontweight="bold")
    ax2.set_ylabel("Signal Detection Sensitivity (d') [Higher is Better]")
    ax2.set_title("(b) User Anomaly Discrimination Sensitivity (d')")
    ax2.set_ylim(-1.05, 5.35)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    for b, v, sd in zip(bars_dp, dp_vals, dp_sds):
        y_txt = (v + sd + 0.16) if v >= 0 else (v - sd - 0.24)
        ax2.text(b.get_x() + b.get_width() / 2, y_txt, f"{v:.2f}", ha="center", va="center", fontsize=8.2, fontweight="bold")

    fig.tight_layout()
    _save(fig, "fig4_pareto_security_workload")

    # -------------------------------------------------------------------------
    # FIGURE 5: Expertise Stratification (Novice vs. Intermediate vs. Security-Aware)
    # -------------------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4.3))
    groups = ["novice", "intermediate", "security_aware"]
    group_labels = ["Novice Users\n(n=16)", "Intermediate Users\n(n=16)", "Security-Aware Users\n(n=16)"]
    x = np.arange(len(groups))
    width = 0.34

    b3_asr = [expertise["B3_BINARY_MODAL"][g]["asr_mean"] for g in groups]
    pg_asr = [expertise["PROV_GUARD_FULL"][g]["asr_mean"] for g in groups]

    b3_dp = [expertise["B3_BINARY_MODAL"][g]["d_prime_mean"] for g in groups]
    pg_dp = [expertise["PROV_GUARD_FULL"][g]["d_prime_mean"] for g in groups]

    r1 = ax1.bar(x - width / 2, b3_asr, width, label="B3: Uniform Binary Modal", color=CORAL_WARN, edgecolor="#1E293B")
    r2 = ax1.bar(x + width / 2, pg_asr, width, label="PROV-Guard (Full Suite)", color=TEAL_ACCENT, edgecolor="#1E293B")
    ax1.set_xticks(x)
    ax1.set_xticklabels(group_labels, fontweight="bold")
    ax1.set_ylabel("Attack Success Rate — ASR (%)")
    ax1.set_title("(a) Attack Susceptibility by User Expertise")
    ax1.set_ylim(0, 118)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend(loc="upper right", framealpha=0.95)
    for bar in list(r1) + list(r2):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    r3 = ax2.bar(x - width / 2, b3_dp, width, label="B3: Uniform Binary Modal", color=CORAL_WARN, edgecolor="#1E293B")
    r4 = ax2.bar(x + width / 2, pg_dp, width, label="PROV-Guard (Full Suite)", color=PRIMARY_NAVY, edgecolor="#1E293B")
    ax2.axhline(0.0, color="#1E293B", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(group_labels, fontweight="bold")
    ax2.set_ylabel("Sensitivity Index (d')")
    ax2.set_title("(b) Discrimination Sensitivity (d') by User Expertise")
    ax2.set_ylim(-0.65, 5.5)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.legend(loc="upper left", framealpha=0.95)
    for bar in list(r3) + list(r4):
        h = bar.get_height()
        y_p = h + 0.16 if h >= 0 else h - 0.32
        ax2.text(bar.get_x() + bar.get_width() / 2, y_p, f"{h:.2f}", ha="center", va="center", fontsize=8.5, fontweight="bold")

    fig.tight_layout()
    _save(fig, "fig5_expertise_stratification")
    print("Regenerated all 5 publication figures cleanly.")


if __name__ == "__main__":
    res_path = Path("/tmp/prov_guard_work/repo/experiments/results/experimental_results.json")
    out_dirs = [
        Path("/tmp/prov_guard_work/repo/figures"),
        Path("/working_dir/c_463bc165502d78a7/repo/figures"),
        Path("/working_dir/c_463bc165502d78a7/artifacts/file_generation/ttl=63d/intermediate"),
    ]
    generate_all_figures(res_path, out_dirs)
