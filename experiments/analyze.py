"""Statistical analysis, tables and figures for the CLEAR evaluation.

Reads results/raw/{episodes,calls}_*.jsonl/.csv.gz (from evaluate.py) and
results/human_sim.csv (from human_sim.py), writes
    results/tables/*.csv and *.tex
    results/stats.json
    figures/*.pdf, *.png

Statistics
----------
* 95% confidence intervals: cluster bootstrap (2,000 resamples) over
  (model, suite, user task) clusters, because episodes of the same user task
  are not independent.
* Paired binary outcomes (same episodes, two policies): exact McNemar test
  (two-sided binomial test on discordant pairs); Holm correction within each
  family of comparisons.
* Paired counts (interruptions per benign episode): Wilcoxon signed-rank test,
  with matched-pairs rank-biserial correlation as effect size.
* Call-level discrimination: AUROC (Mann-Whitney) with cluster-bootstrap CI.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "results" / "raw"
if not any(RAW.glob("episodes_*.jsonl*")):
    RAW = ROOT / "data" / "derived"   # shipped, compressed copy of the replay outputs
TAB = ROOT / "results" / "tables"
FIG = ROOT / "figures"
DEFENCE_SUFFIXES = ("-repeat_user_prompt", "-spotlighting_with_delimiting", "-tool_filter", "-transformers_pi_detector")
RNG = np.random.default_rng(20261026)
N_BOOT = 2000

# reference categorical palette (fixed order; see figures/README.md)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"

POLICY_LABEL = {
    "none:none": "No defence",
    "pi_detector:auto": "Injection detector (abort)",
    "envelope_only:auto": "Task-scoped allowlist (auto)",
    "strict_ifc:auto": "Strict info-flow policy (auto)",
    "confirm_all:oracle": "Confirm-all (ideal user)",
    "confirm_all:auto": "Confirm-all (deny all)",
    "clear:oracle": "CLEAR (ideal user)",
    "clear:auto": "CLEAR (deny escalations)",
}
MAIN_POLICIES = list(POLICY_LABEL)


# --------------------------------------------------------------------------- loading
def load_episodes() -> pd.DataFrame:
    rows = []
    for f in sorted(RAW.glob("episodes_*.jsonl*")):
        with (gzip.open(f, "rt") if f.suffix == ".gz" else open(f)) as fh:
            for line in fh:
                r = json.loads(line)
                if "error" in r:
                    continue
                base = {k: r[k] for k in ("key", "model", "suite", "user_task", "injection_task", "attack",
                                          "attacked", "base_utility", "base_security", "stored_utility",
                                          "stored_security", "n_calls", "n_side_effecting", "n_injected",
                                          "n_sig", "n_necessary", "benchmark_version")}
                for pm, v in r["policies"].items():
                    rows.append({**base, "policy": pm, "u": bool(v["u"]),
                                 "s": (None if v["s"] is None else bool(v["s"])),
                                 "confirm": v["confirm"], "force": v["force"], "notify": v["notify"]})
    df = pd.DataFrame(rows)
    df["pipeline"] = df["model"]
    df["defence"] = "none"
    for suf in DEFENCE_SUFFIXES:
        m = df["model"].str.endswith(suf)
        df.loc[m, "defence"] = suf[1:]
        df.loc[m, "model"] = df.loc[m, "model"].str[: -len(suf)]
    df["dev"] = (df["pipeline"] == "gpt-4o-2024-05-13") & df["suite"].isin(["banking", "slack"])
    df["cluster"] = df["pipeline"] + "|" + df["suite"] + "|" + df["user_task"]
    return df


def load_calls() -> pd.DataFrame:
    parts = []
    for f in sorted(RAW.glob("calls_*.csv.gz")):
        d = pd.read_csv(f, compression="gzip")
        d["pipeline"] = f.name[len("calls_"):-len(".csv.gz")]
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["defence"] = "none"
    for suf in DEFENCE_SUFFIXES:
        df.loc[df["pipeline"].str.endswith(suf), "defence"] = suf[1:]
    df["dev"] = (df["pipeline"] == "gpt-4o-2024-05-13") & df["suite"].isin(["banking", "slack"])
    df["cluster"] = df["pipeline"] + "|" + df["key"].str.split("|").str[1] + "|" + df["key"].str.split("|").str[2]
    return df


# --------------------------------------------------------------------------- statistics helpers
def cluster_boot(df: pd.DataFrame, fn, n=N_BOOT) -> tuple[float, float, float]:
    """Point estimate and percentile CI of fn(df) under cluster resampling."""
    point = fn(df)
    groups = {k: g.index.to_numpy() for k, g in df.groupby("cluster")}
    keys = list(groups)
    if len(keys) < 2:
        return point, np.nan, np.nan
    vals = []
    for _ in range(n):
        pick = RNG.integers(0, len(keys), len(keys))
        idx = np.concatenate([groups[keys[i]] for i in pick])
        vals.append(fn(df.loc[idx]))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return point, lo, hi


def boot_mean(df: pd.DataFrame, col: str, n=N_BOOT) -> tuple[float, float, float]:
    """Fast cluster bootstrap for a mean (ratio of resampled cluster sums)."""
    if df.empty:
        return np.nan, np.nan, np.nan
    g = df.groupby("cluster")[col].agg(["sum", "count"])
    sums, cnts = g["sum"].to_numpy(float), g["count"].to_numpy(float)
    point = sums.sum() / cnts.sum()
    pick = RNG.integers(0, len(g), size=(n, len(g)))
    vals = sums[pick].sum(1) / cnts[pick].sum(1)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(point), float(lo), float(hi)


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> dict:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n01 = int(np.sum(~a & b))   # a false, b true
    n10 = int(np.sum(a & ~b))
    n = n01 + n10
    p = 1.0 if n == 0 else stats.binomtest(n10, n, 0.5).pvalue
    return {"n10": n10, "n01": n01, "p": p, "diff": float(a.mean() - b.mean()), "n": int(len(a))}


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def wilcoxon_paired(x, y) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = x - y
    nz = d[d != 0]
    if len(nz) == 0:
        return {"W": 0.0, "p": 1.0, "r_rb": 0.0, "n_nonzero": 0}
    res = stats.wilcoxon(nz)
    ranks = stats.rankdata(np.abs(nz))
    r_plus, r_minus = ranks[nz > 0].sum(), ranks[nz < 0].sum()
    return {"W": float(res.statistic), "p": float(res.pvalue), "r_rb": float((r_plus - r_minus) / ranks.sum()),
            "n_nonzero": int(len(nz))}


def auroc(scores, labels) -> float:
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def fmt_ci(p, lo, hi, pct=True, nd=1):
    if pct:
        return f"{100 * p:.{nd}f} [{100 * lo:.{nd}f}, {100 * hi:.{nd}f}]"
    return f"{p:.2f} [{lo:.2f}, {hi:.2f}]"


# --------------------------------------------------------------------------- tables
def policy_metrics(ep: pd.DataFrame, calls: pd.DataFrame, policies, label_fn=lambda p: POLICY_LABEL.get(p, p)):
    out = []
    att = ep[ep.attacked]
    ben = ep[~ep.attacked]
    for pol in policies:
        a = att[att.policy == pol].reset_index(drop=True)
        b = ben[ben.policy == pol].reset_index(drop=True)
        a = a.assign(s=a["s"].astype(float), u=a["u"].astype(float))
        b = b.assign(u=b["u"].astype(float))
        asr, ua = boot_mean(a, "s"), boot_mean(a, "u")
        bu, ib = boot_mean(b, "u"), boot_mean(b, "confirm")
        ia = a["confirm"].mean()
        out.append({"policy": pol, "label": label_fn(pol), "n_attacked": len(a), "n_benign": len(b),
                    "ASR": asr[0], "ASR_lo": asr[1], "ASR_hi": asr[2],
                    "UA": ua[0], "UA_lo": ua[1], "UA_hi": ua[2],
                    "BU": bu[0], "BU_lo": bu[1], "BU_hi": bu[2],
                    "int_benign": ib[0], "int_benign_lo": ib[1], "int_benign_hi": ib[2], "int_attacked": ia})
    return pd.DataFrame(out)


def call_level(calls: pd.DataFrame, variant: str) -> dict:
    se = calls[calls.side_effecting == 1]
    inj = se[se.injected == 1]
    ben = se[se.injected == 0]
    col = f"tier_{variant}"
    return {"variant": variant,
            "escalation_recall": float((inj[col] >= 2).mean()),
            "force_share_injected": float((inj[col] == 3).mean()),
            "false_escalation_rate": float((ben[col] >= 2).mean()),
            "force_share_benign": float((ben[col] == 3).mean()),
            "auroc": auroc(se[f"risk_{variant}"], se.injected == 1),
            "n_injected_calls": int(len(inj)), "n_benign_calls": int(len(ben))}


def paired_tests(ep: pd.DataFrame, ref: str, others: list[str], metric: str, subset: str) -> pd.DataFrame:
    d = ep[ep.attacked] if subset == "attacked" else ep[~ep.attacked]
    piv = d.pivot_table(index="key", columns="policy", values=metric, aggfunc="first")
    rows = []
    for o in others:
        sub = piv[[ref, o]].dropna()
        rows.append({"comparison": f"{ref} vs {o}", "metric": metric, **mcnemar_exact(sub[ref].astype(bool),
                                                                                      sub[o].astype(bool))})
    res = pd.DataFrame(rows)
    res["p_holm"] = holm(res["p"].tolist())
    return res


def to_latex(df: pd.DataFrame, path: Path, caption: str, label: str, colfmt: str | None = None) -> None:
    cols = list(df.columns)
    colfmt = colfmt or ("l" + "r" * (len(cols) - 1))
    lines = [r"\begin{table}[t]", r"\centering", r"\small", rf"\caption{{{caption}}}", rf"\label{{{label}}}",
             r"\resizebox{\linewidth}{!}{%", rf"\begin{{tabular}}{{{colfmt}}}", r"\toprule", " & ".join(cols) + r" \\", r"\midrule"]
    esc = lambda v: str(v).replace("%", r"\%").replace("_", r"\_")  # noqa: E731
    lines[8] = " & ".join(esc(c) for c in cols) + r" \\"
    for _, r in df.iterrows():
        lines.append(" & ".join(esc(v) for v in r.values) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}", r"\end{table}"]
    path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- figures
def setup_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
        "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
        "savefig.bbox": "tight", "savefig.dpi": 300, "pdf.fonttype": 42,
    })
    return plt


def fig_tradeoff(main: pd.DataFrame, plt):
    fig, ax = plt.subplots(figsize=(5.4, 3.4))
    m = main.set_index("policy")
    pts = [  # (policy for position, label, colour, marker, BU text)
        ("none:none", "No defence", MUTED, "o", f"BU {100 * m.loc['none:none'].BU:.0f}%"),
        ("envelope_only:auto", "Task-scoped allowlist", C[2], "D", f"BU {100 * m.loc['envelope_only:auto'].BU:.0f}%"),
        ("strict_ifc:auto", "Strict info-flow policy", C[6], "P", f"BU {100 * m.loc['strict_ifc:auto'].BU:.0f}%"),
        ("pi_detector:auto", "Injection detector (abort)", C[3], "s",
         f"BU {100 * m.loc['pi_detector:auto'].BU:.0f}%, UA {100 * m.loc['pi_detector:auto'].UA:.0f}%"),
        ("clear:oracle", "CLEAR", C[0], "*",
         f"BU {100 * m.loc['clear:oracle'].BU:.0f}% ideal user / {100 * m.loc['clear:auto'].BU:.0f}% deny-all"),
        ("confirm_all:oracle", "Confirm-all", C[1], "^",
         f"BU {100 * m.loc['confirm_all:oracle'].BU:.0f}% ideal user / {100 * m.loc['confirm_all:auto'].BU:.0f}% deny-all"),
    ]
    offs = {"none:none": (6, -2), "envelope_only:auto": (6, -2), "strict_ifc:auto": (6, 2),
            "pi_detector:auto": (6, -14), "clear:oracle": (-30, 14), "confirm_all:oracle": (-120, 46)}
    for pol, lab, col, mk, bu in pts:
        r = m.loc[pol]
        ax.errorbar(r.int_benign, 100 * r.ASR, yerr=[[100 * (r.ASR - r.ASR_lo)], [100 * (r.ASR_hi - r.ASR)]],
                    xerr=[[r.int_benign - r.int_benign_lo], [r.int_benign_hi - r.int_benign]],
                    fmt=mk, color=col, ms=11 if mk == "*" else 7, mec="white", mew=0.8, elinewidth=1, capsize=0)
        ax.annotate(f"{lab}\n{bu}", (r.int_benign, 100 * r.ASR), xytext=offs[pol], textcoords="offset points",
                    fontsize=7, color=INK)
    ax.set_xlabel("Confirmation dialogs per benign task (user burden)")
    ax.set_ylabel("Attack success rate (%)")
    ax.set_xlim(-0.05, 0.95)
    ax.set_ylim(-1.5, 19)
    fig.savefig(FIG / "fig_tradeoff.pdf")
    fig.savefig(FIG / "fig_tradeoff.png")
    plt.close(fig)


def fig_per_model(per_model: pd.DataFrame, plt):
    d = per_model.sort_values("ASR_none", ascending=True)
    fig, ax = plt.subplots(figsize=(5.2, 0.24 * len(d) + 0.8))
    y = np.arange(len(d))
    h = 0.26
    ax.barh(y + h, 100 * d.ASR_none, h * 0.9, color=MUTED, label="No defence")
    ax.barh(y, 100 * d.ASR_clear_auto, h * 0.9, color=C[0], label="CLEAR, escalations denied")
    ax.barh(y - h, 100 * d.ASR_clear_oracle, h * 0.9, color=C[1], label="CLEAR, ideal user")
    ax.set_yticks(y, d.model, fontsize=7)
    ax.set_xlabel("Attack success rate (%), held-out episodes")
    ax.legend(loc="lower right", fontsize=7)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG / "fig_per_model.pdf")
    fig.savefig(FIG / "fig_per_model.png")
    plt.close(fig)


def roc_points(scores, labels):
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    order = np.argsort(-scores, kind="mergesort")
    s, l = scores[order], labels[order]
    tps = np.cumsum(l)
    fps = np.cumsum(~l)
    distinct = np.r_[np.where(np.diff(s))[0], len(s) - 1]
    tpr = np.r_[0, tps[distinct] / max(l.sum(), 1)]
    fpr = np.r_[0, fps[distinct] / max((~l).sum(), 1)]
    return fpr, tpr


def fig_roc_plot(calls: pd.DataFrame, variants: dict[str, str], plt):
    se = calls[calls.side_effecting == 1]
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    for i, (v, lab) in enumerate(variants.items()):
        fpr, tpr = roc_points(se[f"risk_{v}"], se.injected == 1)
        ax.plot(fpr, tpr, color=C[i], lw=1.6, label=f"{lab} (AUC {auroc(se[f'risk_{v}'], se.injected == 1):.3f})")
    ax.plot([0, 1], [0, 1], color=GRID, lw=1, ls="--")
    ax.set_xlabel("False escalation rate (benign calls)")
    ax.set_ylabel("Detection rate (injected calls)")
    ax.legend(fontsize=6.5, loc="lower right")
    fig.savefig(FIG / "fig_roc.pdf")
    fig.savefig(FIG / "fig_roc.png")
    plt.close(fig)


def fig_curves(curves: pd.DataFrame, main: pd.DataFrame, plt):
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    sty = {"CLEAR": (C[0], "-", "o"), "CLEAR, detector-evading attacker": (C[0], "--", "s"),
           "No provenance": (C[1], "-", "o"), "No provenance, detector-evading attacker": (C[1], "--", "s")}
    for name, d in curves.groupby("variant"):
        col, ls, mk = sty[name]
        d = d.sort_values("dialogs_benign")
        ax.plot(d.dialogs_benign, 100 * d.ASR, color=col, ls=ls, marker=mk, ms=4, lw=1.6, label=name)
        dflt = d[d.threshold_scale == 1.0]
        ax.plot(dflt.dialogs_benign, 100 * dflt.ASR, marker="*", ms=11, color=col, mec="white", mew=0.8, ls="none")
    ca = main[main.policy == "confirm_all:oracle"].iloc[0]
    nd = main[main.policy == "none:none"].iloc[0]
    ax.plot(ca.int_benign, 100 * ca.ASR, marker="^", ms=8, color=C[6], ls="none", label="Confirm-all")
    ax.axhline(100 * nd.ASR, color=MUTED, lw=1, ls=":")
    ax.text(0.02, 100 * nd.ASR + 0.4, "no defence", color=MUTED, fontsize=7)
    ax.set_xlabel("Confirmation dialogs per benign task")
    ax.set_ylabel("Attack success rate (%), ideal user")
    ax.legend(fontsize=6.5, loc="center right")
    fig.savefig(FIG / "fig_curves.pdf")
    fig.savefig(FIG / "fig_curves.png")
    plt.close(fig)


def fig_tiers(calls: pd.DataFrame, plt):
    se = calls[(calls.side_effecting == 1) & (calls.defence == "none")]
    groups = {"Injected calls": se[se.injected == 1],
              "Benign calls,\nattacked episodes": se[(se.injected == 0) & (se.attack != "none")],
              "Benign calls,\nclean episodes": se[se.attack == "none"]}
    tiers = ["ALLOW", "NOTIFY", "CONFIRM", "FORCE"]
    cols = ["#b9b8b2", C[0], C[3], C[7]]
    fig, ax = plt.subplots(figsize=(5.2, 1.9))
    for gi, (g, d) in enumerate(groups.items()):
        left = 0.0
        shares = [(d.tier_clear == t).mean() for t in range(4)]
        for ti, sh in enumerate(shares):
            ax.barh(gi, 100 * sh, left=left, color=cols[ti], edgecolor="white", linewidth=1.5,
                    label=tiers[ti] if gi == 0 else None)
            if sh > 0.06:
                ax.text(left + 50 * sh, gi, f"{100 * sh:.0f}%", ha="center", va="center", fontsize=7, color=INK)
            left += 100 * sh
    ax.set_yticks(range(3), list(groups), fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Share of side-effecting calls (%)")
    ax.legend(ncol=4, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.32))
    ax.grid(axis="y", visible=False)
    fig.savefig(FIG / "fig_tiers.pdf")
    fig.savefig(FIG / "fig_tiers.png")
    plt.close(fig)


def fig_human(hs: pd.DataFrame, plt):
    lam = hs[hs.sweep == "lam"].copy()
    lam["lam_plot"] = lam["lam"].replace(np.inf, 200.0)
    names = {"confirm_all": ("Confirm-all, generic dialog", C[1], "^"),
             "confirm_all_evidence": ("Confirm-all, with provenance", C[3], "v"),
             "clear_no_evidence": ("CLEAR escalation, generic dialog", C[2], "s"),
             "clear": ("CLEAR (escalation + evidence + forcing)", C[0], "o")}
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
    for pol, (lab, col, mk) in names.items():
        d = lam[lam.policy == pol].sort_values("lam_plot")
        axes[0].plot(d.lam_plot, 100 * d.e2e_asr, color=col, marker=mk, ms=5, lw=1.6, label=lab)
    axes[0].set_xscale("log")
    axes[0].set_xticks([3, 7, 15, 30, 60, 200], ["3", "7", "15", "30", "60", "none"])
    axes[0].set_xlabel(r"Habituation time constant $\lambda$ (dialogs)")
    axes[0].set_ylabel("End-to-end ASR (%)")
    dp = hs[hs.sweep == "d_prov"]
    for pol, (lab, col, mk) in names.items():
        d = dp[dp.policy == pol].sort_values("d_prov")
        axes[1].plot(d.d_prov, 100 * d.e2e_asr, color=col, marker=mk, ms=5, lw=1.6, label=lab)
    axes[1].set_xlabel(r"Sensitivity gain from provenance evidence $\Delta d'_{prov}$")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, fontsize=7, bbox_to_anchor=(0.5, -0.24))
    fig.suptitle("Simulated users (parametric model, not human data)", fontsize=8, color=MUTED)
    fig.savefig(FIG / "fig_human_sim.pdf")
    fig.savefig(FIG / "fig_human_sim.png")
    plt.close(fig)


# --------------------------------------------------------------------------- offline operating curves
def load_subset_outcomes(keys: set[str]) -> dict[str, dict]:
    out = {}
    for f in sorted(RAW.glob("episodes_*.jsonl*")):
        with (gzip.open(f, "rt") if f.suffix == ".gz" else open(f)) as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("key") in keys and "error" not in r:
                    out[r["key"]] = {"subset_outcomes": r.get("subset_outcomes"), "subset_calls": r.get("subset_calls"),
                                     "base_security": r["base_security"]}
    return out


def tiers_from_features(c: pd.DataFrame, cfg: dict, scale: float = 1.0, zero: tuple[str, ...] = ()) -> np.ndarray:
    """Recompute CLEAR tiers from logged features (vectorised clear/risk.py)."""
    r, t = cfg["risk"], cfg["tiers"]
    x = {k: c[f"f_{k}"].fillna(0).to_numpy(float) for k in ("tau", "kappa", "delta", "iota")}
    for z in zero:
        x[z] = np.zeros(len(c))
    w = {"tau": r["w_taint"], "kappa": r["w_exfil"], "delta": r["w_deviation"], "iota": r["w_injection"]}
    rem = np.ones(len(c))
    for k in x:
        rem *= 1 - w[k] * x[k]
    risk = c["sensitivity"].to_numpy(float) * (1 - rem)
    side = c["side_effecting"].to_numpy(bool) | (c["sensitivity"].to_numpy(float) > 0)
    risk = np.where(side, risk, 0.0)
    rev = c["reversible"].to_numpy(bool)
    tier = np.zeros(len(c), int)
    tier[risk >= scale * t["notify"]] = 1
    tier[(risk >= scale * t["notify"]) & ~rev & t.get("promote_irreversible_notify", True)] = 2
    tier[risk >= scale * t["confirm"]] = 2
    tier[risk >= scale * t["force"]] = 3
    return tier


def oracle_outcomes(att_calls: pd.DataFrame, ben_calls: pd.DataFrame, subsets: dict, att_tier, ben_tier) -> dict:
    """Exact ideal-user ASR (via stored subset outcomes) and dialogs per benign task."""
    a = att_calls.assign(tier=att_tier)
    esc_inj = a[(a.tier >= 2) & (a.injected == 1)].groupby("key").idx.apply(lambda s: sorted(set(s)))
    succ = []
    for key, rec in subsets.items():
        if rec["subset_outcomes"] is None:
            continue
        allowed = set(rec["subset_calls"])
        denied = [i for i in esc_inj.get(key, []) if i in allowed]
        succ.append(bool(rec["subset_outcomes"][",".join(map(str, denied))][1]))
    b = ben_calls.assign(tier=ben_tier)
    dialogs = b.groupby("key").tier.apply(lambda s: int((s >= 2).sum()))
    return {"ASR": float(np.mean(succ)), "n": len(succ), "dialogs_benign": float(dialogs.mean())}


# --------------------------------------------------------------------------- manuscript artefacts
def pct(x, nd=1):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{nd}f}"


def write_paper_tables(st: dict, main: pd.DataFrame, pub: pd.DataFrame, at: pd.DataFrame, pm: pd.DataFrame,
                       curves: pd.DataFrame, core: pd.DataFrame) -> None:
    m = main.set_index("policy")
    macros = {}
    def mac(name, val):
        macros[name] = val
    d = st["dataset"]
    mac("nEpisodes", f"{d['episodes']:,}".replace(",", "{,}"))
    mac("nAttacked", f"{d['attacked_episodes']:,}".replace(",", "{,}"))
    mac("nBenign", f"{d['benign_episodes']:,}".replace(",", "{,}"))
    mac("nCalls", f"{d['tool_calls']:,}".replace(",", "{,}"))
    mac("nSideCalls", f"{d['side_effecting_calls']:,}".replace(",", "{,}"))
    mac("nInjCalls", f"{d['injected_calls']:,}".replace(",", "{,}"))
    mac("nPipelines", str(d["pipelines"]))
    mac("nModels", str(d["models"]))
    mac("fidU", pct(d["replay_agreement_utility_mean"]))
    mac("fidS", pct(d["replay_agreement_security_mean"]))
    mac("fidUmin", pct(d["replay_agreement_utility_min"]))
    mac("labelKappa", f"{st['label_agreement']['cohen_kappa']:.2f}")
    mac("labelAgree", pct(st["label_agreement"]["percent_agreement"]))
    mac("nHeldAtt", f"{int(m.loc['none:none'].n_attacked):,}".replace(",", "{,}"))
    mac("nHeldBen", f"{int(m.loc['none:none'].n_benign):,}".replace(",", "{,}"))
    for key, name in [("none:none", "None"), ("clear:oracle", "ClearO"), ("clear:auto", "ClearA"),
                      ("confirm_all:oracle", "CallO"), ("confirm_all:auto", "CallA"), ("strict_ifc:auto", "Ifc"),
                      ("envelope_only:auto", "Env"), ("pi_detector:auto", "Det")]:
        r = m.loc[key]
        mac(f"asr{name}", pct(r.ASR, 2 if r.ASR < 0.1 else 1))
        mac(f"asr{name}CI", f"[{pct(r.ASR_lo, 2)}, {pct(r.ASR_hi, 2)}]")
        mac(f"bu{name}", pct(r.BU))
        mac(f"ua{name}", pct(r.UA))
        mac(f"dlg{name}", f"{r.int_benign:.2f}")
        mac(f"dlgAtt{name}", f"{r.int_attacked:.2f}")
    w = st["interruptions_wilcoxon"]
    mac("dlgReduction", pct(w["reduction_ratio"], 0))
    mac("noDialogClear", pct(w["share_benign_tasks_without_dialog_clear"], 0))
    mac("noDialogCall", pct(w["share_benign_tasks_without_dialog_confirm_all"], 0))
    mac("wilcoxP", f"{w['clear_vs_confirm_all']['p']:.1e}".replace("e-", r"\times10^{-") + "}")
    cl = {r["variant"]: r for r in st["call_level"]}
    mac("recall", pct(cl["clear"]["escalation_recall"]))
    mac("fer", pct(cl["clear"]["false_escalation_rate"]))
    mac("forceInj", pct(cl["clear"]["force_share_injected"], 0))
    mac("forceBen", pct(cl["clear"]["force_share_benign"], 0))
    mac("auroc", f"{st['auroc_clear']['point']:.3f}")
    mac("aurocCI", f"[{st['auroc_clear']['lo']:.3f}, {st['auroc_clear']['hi']:.3f}]")
    mac("aurocNoProv", f"{cl['clear_no_provenance']['auroc']:.3f}")
    lat = st["latency_ms"]
    mac("latMed", f"{lat['median']:.3f}")
    mac("latPnn", f"{lat['p99']:.2f}")
    mac("latMax", f"{lat['max']:.1f}")
    cv = curves.set_index(["variant", "threshold_scale"])
    mac("asrEvadeClear", pct(cv.loc[("CLEAR, detector-evading attacker", 1.0)].ASR, 2))
    mac("asrEvadeNoProvMin", pct(curves[curves.variant == "No provenance, detector-evading attacker"].ASR.min(), 1))
    mac("asrNoProvLow", pct(cv.loc[("No provenance", 0.25)].ASR, 2))
    mac("dlgNoProvLow", f"{cv.loc[('No provenance', 0.25)].dialogs_benign:.2f}")
    # residual analysis
    r = core[(core.policy == "clear:oracle") & (core.s == True)]  # noqa: E712
    mac("residualN", str(len(r)))
    mac("residualOutputOnly", str(int((r.n_injected == 0).sum())))
    nonout = core[(core.policy == "clear:oracle") & core.attacked & (core.injection_task != "injection_task_6") | (
        (core.policy == "clear:oracle") & core.attacked & (core.suite != "travel"))]
    mac("asrClearOExclOut", pct(nonout.s.astype(float).mean(), 2))
    hs = st.get("human_sim")
    if hs:
        dflt = {r["policy"]: r for r in hs["default"]}
        for k, n in [("confirm_all", "Call"), ("confirm_all_evidence", "CallEv"), ("clear_no_evidence", "ClearNoEv"), ("clear", "Clear")]:
            mac(f"sim{n}", pct(dflt[k]["e2e_asr"]))
            mac(f"simAcc{n}", pct(dflt[k]["dialog_accuracy"]))
            mac(f"simBU{n}", pct(dflt[k]["benign_utility"]))
        mac("simGridN", str(hs["grid_points"]))
        mac("simShare", pct(hs["share_clear_lower_asr_than_confirm_all"], 0))
        mac("simShareNoEv", pct(hs["share_clear_no_evidence_lower_asr_than_confirm_all"], 1))
        mac("simMedClear", pct(hs["median_asr_clear"]))
        mac("simMedCall", pct(hs["median_asr_confirm_all"]))
    with open(TAB / "numbers.tex", "w") as fh:
        fh.write("% generated by experiments/analyze.py -- do not edit\n")
        for k, v in macros.items():
            fh.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")

    # published defences table
    lab = {"none": "none (undefended)", "repeat_user_prompt": "sandwich (repeat user prompt)",
           "spotlighting_with_delimiting": "spotlighting (delimiting)", "tool_filter": "tool filter",
           "transformers_pi_detector": "DeBERTa PI detector"}
    rows = []
    for pipe in ["gpt-4o-2024-05-13", "gpt-4o-2024-05-13-repeat_user_prompt", "gpt-4o-2024-05-13-spotlighting_with_delimiting",
                 "gpt-4o-2024-05-13-tool_filter", "gpt-4o-2024-05-13-transformers_pi_detector",
                 "meta-llama_Llama-3.3-70B-Instruct", "meta-llama_Llama-3.3-70B-Instruct-repeat_user_prompt",
                 "Meta-SecAlign-70B", "Meta-SecAlign-70B-repeat_user_prompt"]:
        d = pub[pub.pipeline == pipe].set_index("policy")
        if d.empty:
            continue
        model = {"gpt-4o-2024-05-13": "GPT-4o", "meta-llama_Llama-3.3-70B-Instruct": "Llama-3.3-70B",
                 "Meta-SecAlign-70B": "Meta-SecAlign-70B"}[d.model.iloc[0]]
        rows.append([model, lab[d.defence.iloc[0]], pct(d.loc["none:none"].ASR), pct(d.loc["none:none"].BU),
                     pct(d.loc["clear:oracle"].ASR), f"{d.loc['clear:oracle'].dialogs_benign:.2f}",
                     pct(d.loc["clear:auto"].ASR), pct(d.loc["clear:auto"].BU)])
    lines = [r"\begin{tabular}{llrrrrrr}", r"\toprule",
             r" & & \multicolumn{2}{c}{Published defence alone} & \multicolumn{2}{c}{+ CLEAR, ideal user} & \multicolumn{2}{c}{+ CLEAR, deny escalations}\\",
             r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-8}",
             r"Model & Defence & ASR\,\% & BU\,\% & ASR\,\% & Dialogs & ASR\,\% & BU\,\% \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "published_defences.tex").write_text("\n".join(lines) + "\n")

    # attack types
    names = {"important_instructions": "important instructions", "tool_knowledge": "tool knowledge",
             "ignore_previous": "ignore previous", "direct": "direct (TODO)", "injecagent": "InjecAgent"}
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"Attack & No defence & Lexical detector & CLEAR $-\iota$ (ideal) & CLEAR (ideal) & CLEAR (deny) \\", r"\midrule"]
    for _, r in at.iterrows():
        lines.append(f"{names[r.attack]} & {pct(r['none:none'])} & {pct(r['pi_detector:auto'])} & "
                     f"{pct(r['clear_no_injection:oracle'])} & {pct(r['clear:oracle'])} & {pct(r['clear:auto'])} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "attack_types.tex").write_text("\n".join(lines) + "\n")

    # per-model table
    lines = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
             r"Model & $n$ & ASR none & ASR CLEAR & BU none & Dialogs CLEAR & Dialogs confirm-all \\", r"\midrule"]
    for _, r in pm.sort_values("ASR_none", ascending=False).iterrows():
        lines.append(f"{r.model.replace('meta-llama_', '').replace('_', '-')} & {int(r.n_attacked)} & {pct(r.ASR_none)} & "
                     f"{pct(r.ASR_clear_oracle)} & {pct(r.BU_none)} & {r.dialogs_clear:.2f} & {r.dialogs_confirm_all:.2f} \\\\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "per_model.tex").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- main
def main() -> None:
    TAB.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    ep = load_episodes()
    calls = load_calls()
    statsout: dict = {}

    # ------------------------------------------------ dataset description & fidelity
    base = ep[(ep.policy == "none:none")]
    fid = []
    for f in sorted(RAW.glob("summary_*.json")):
        s = json.loads(f.read_text())
        d = base[base.pipeline == s["model"]]
        att = d[d.attacked]
        fid.append({"pipeline": s["model"], "benchmark_version": s["version"], "episodes": len(d),
                    "attacked": len(att), "errors": s["errors"],
                    "agree_utility": float((d.base_utility == d.stored_utility).mean()),
                    "agree_security": float((att.base_security == att.stored_security).mean()) if len(att) else np.nan})
    fid = pd.DataFrame(fid)
    fid.to_csv(TAB / "replay_fidelity.csv", index=False)
    statsout["dataset"] = {
        "pipelines": int(base.pipeline.nunique()), "models": int(base[base.defence == "none"].model.nunique()),
        "episodes": int(len(base)), "attacked_episodes": int(base.attacked.sum()),
        "benign_episodes": int((~base.attacked).sum()), "tool_calls": int(len(calls)),
        "side_effecting_calls": int((calls.side_effecting == 1).sum()),
        "injected_calls": int((calls.injected == 1).sum()),
        "replay_agreement_utility_mean": float((fid.agree_utility * fid.episodes).sum() / fid.episodes.sum()),
        "low_fidelity_pipelines": fid[(fid.agree_utility < 0.95) | (fid.agree_security < 0.95)].pipeline.tolist(),
        "replay_agreement_security_mean": float((fid.agree_security * fid.attacked).sum() / fid.attacked.sum()),
        "replay_agreement_security_min": float(fid.agree_security.min()),
        "replay_agreement_utility_min": float(fid.agree_utility.min()),
        "episodes_with_errors": int(fid.errors.sum()),
    }

    # label agreement (signature vs necessity) on side-effecting calls of successful attacks
    se_att = calls[(calls.side_effecting == 1) & (calls.attack != "none")]
    succ_keys = set(base[base.attacked & (base.base_security == True)].key)  # noqa: E712
    la = se_att[se_att.key.isin(succ_keys)]
    po = float((la.sig == la.necessary).mean())
    pe = float(la.sig.mean() * la.necessary.mean() + (1 - la.sig.mean()) * (1 - la.necessary.mean()))
    statsout["label_agreement"] = {"n_calls": int(len(la)), "percent_agreement": po,
                                   "cohen_kappa": (po - pe) / (1 - pe) if pe < 1 else 1.0}

    # ------------------------------------------------ main comparison: important_instructions, held-out
    core = ep[(ep.defence == "none") & (ep.attack.isin(["important_instructions", "none"])) & (~ep.dev)]
    core_calls = calls[(calls.defence == "none") & (calls.attack.isin(["important_instructions", "none"])) & (~calls.dev)]
    main = policy_metrics(core, core_calls, MAIN_POLICIES)
    main.to_csv(TAB / "main_results.csv", index=False)
    tex = main.assign(**{
        "ASR %": [fmt_ci(r.ASR, r.ASR_lo, r.ASR_hi) for r in main.itertuples()],
        "Utility under attack %": [fmt_ci(r.UA, r.UA_lo, r.UA_hi) for r in main.itertuples()],
        "Benign utility %": [fmt_ci(r.BU, r.BU_lo, r.BU_hi) for r in main.itertuples()],
        "Dialogs / benign task": [fmt_ci(r.int_benign, r.int_benign_lo, r.int_benign_hi, pct=False) for r in main.itertuples()],
    })[["label", "ASR %", "Utility under attack %", "Benign utility %", "Dialogs / benign task"]]
    tex = tex.rename(columns={"label": "Policy"})
    to_latex(tex, TAB / "main_results.tex",
             "Held-out evaluation (22 LLM agents; development split excluded; \\texttt{important\\_instructions} attack). "
             "Point estimates with 95\\% cluster-bootstrap confidence intervals (clusters: model $\\times$ user task).", "tab:main", "lrrrr")
    statsout["main"] = main.to_dict(orient="records")

    # paired significance tests
    refs = {"clear:oracle": ["none:none", "pi_detector:auto", "envelope_only:auto", "strict_ifc:auto", "confirm_all:oracle"],
            "clear:auto": ["none:none", "pi_detector:auto", "envelope_only:auto", "strict_ifc:auto", "confirm_all:auto"]}
    tests = []
    for ref, others in refs.items():
        tests.append(paired_tests(core, ref, others, "s", "attacked"))
        tests.append(paired_tests(core, ref, others, "u", "benign"))
        tests.append(paired_tests(core, ref, others, "u", "attacked"))
    tests = pd.concat(tests, ignore_index=True)
    tests.to_csv(TAB / "paired_tests.csv", index=False)
    statsout["paired_tests"] = tests.to_dict(orient="records")
    bpiv = core[~core.attacked].pivot_table(index="key", columns="policy", values="confirm", aggfunc="first")
    statsout["interruptions_wilcoxon"] = {
        "clear_vs_confirm_all": wilcoxon_paired(bpiv["clear:oracle"], bpiv["confirm_all:oracle"]),
        "reduction_ratio": float(1 - bpiv["clear:oracle"].mean() / bpiv["confirm_all:oracle"].mean()),
        "share_benign_tasks_without_dialog_clear": float((bpiv["clear:oracle"] == 0).mean()),
        "share_benign_tasks_without_dialog_confirm_all": float((bpiv["confirm_all:oracle"] == 0).mean()),
    }
    apiv = core[core.attacked].pivot_table(index="key", columns="policy", values="confirm", aggfunc="first")
    statsout["interruptions_attacked_wilcoxon"] = wilcoxon_paired(apiv["clear:oracle"], apiv["confirm_all:oracle"])

    # ------------------------------------------------ sensitivity: drop low-fidelity pipelines
    low = set(statsout["dataset"]["low_fidelity_pipelines"])
    sens = policy_metrics(core[~core.pipeline.isin(low)], core_calls, ["none:none", "confirm_all:oracle", "clear:oracle", "clear:auto"])
    sens.to_csv(TAB / "sensitivity_high_fidelity.csv", index=False)
    statsout["sensitivity_high_fidelity"] = sens.to_dict(orient="records")

    # ------------------------------------------------ all-suites view (incl. dev) for completeness
    allv = ep[(ep.defence == "none") & (ep.attack.isin(["important_instructions", "none"]))]
    allm = policy_metrics(allv, calls, MAIN_POLICIES)
    allm.to_csv(TAB / "main_results_all_suites.csv", index=False)

    # ------------------------------------------------ call-level detection & tiers
    variants = ["clear", "clear_no_provenance", "clear_no_taint", "clear_no_exfil", "clear_no_deviation",
                "clear_no_injection", "clear_single_tier", "clear_gt_envelope"]
    cl = pd.DataFrame([call_level(core_calls, v) for v in variants])
    # bootstrap CI for AUROC of full CLEAR
    se = core_calls[core_calls.side_effecting == 1].reset_index(drop=True)
    au = cluster_boot(se, lambda d: auroc(d.risk_clear, d.injected == 1), n=1000)
    statsout["auroc_clear"] = {"point": au[0], "lo": au[1], "hi": au[2]}
    cl.to_csv(TAB / "call_level.csv", index=False)
    statsout["call_level"] = cl.to_dict(orient="records")

    # ------------------------------------------------ ablations (episode level)
    abl_pols = []
    for v in variants:
        abl_pols += [f"{v}:oracle", f"{v}:auto"]
    abl = policy_metrics(core, core_calls, abl_pols, label_fn=lambda p: p)
    abl.to_csv(TAB / "ablations.csv", index=False)
    rows = []
    for v in variants:
        o = abl[abl.policy == f"{v}:oracle"].iloc[0]
        a = abl[abl.policy == f"{v}:auto"].iloc[0]
        c = cl[cl.variant == v].iloc[0]
        names = {"clear": "CLEAR (full)", "clear_no_provenance": "-- provenance ($\\tau,\\kappa$)",
                 "clear_no_taint": "-- taint ($\\tau$)", "clear_no_exfil": "-- exfiltration ($\\kappa$)",
                 "clear_no_deviation": "-- envelope deviation ($\\delta$)", "clear_no_injection": "-- instruction signal ($\\iota$)",
                 "clear_single_tier": "single threshold (no tiers)", "clear_gt_envelope": "oracle intent envelope"}
        rows.append({"Variant": names[v],
                     "ASR ideal %": f"{100 * o.ASR:.1f}", "ASR auto %": f"{100 * a.ASR:.1f}",
                     "BU auto %": f"{100 * a.BU:.1f}", "Dialogs/benign": f"{o.int_benign:.2f}",
                     "Recall %": f"{100 * c.escalation_recall:.1f}", "FER %": f"{100 * c.false_escalation_rate:.1f}",
                     "AUROC": f"{c.auroc:.3f}"})
    to_latex(pd.DataFrame(rows), TAB / "ablations.tex",
             "Ablations on held-out episodes. Recall: share of injected side-effecting calls escalated to CONFIRM or "
             "FORCE; FER: false escalation rate on benign side-effecting calls.", "tab:ablation", "lrrrrrrr")
    abl_tests = paired_tests(core, "clear:oracle", [f"{v}:oracle" for v in variants[1:]], "s", "attacked")
    abl_tests.to_csv(TAB / "ablation_tests.csv", index=False)
    statsout["ablation_tests"] = abl_tests.to_dict(orient="records")

    # ------------------------------------------------ adaptive (detector-evading) attacker
    # Under this attacker every lexical signal is zero: the abort-detector never fires
    # (its ASR equals the undefended ASR) and CLEAR runs without its injection feature.
    adap = policy_metrics(core, core_calls, ["none:none", "clear_no_injection:oracle", "clear_no_injection:auto"],
                          label_fn=lambda p: p)
    adap.to_csv(TAB / "adaptive.csv", index=False)
    statsout["adaptive"] = adap.to_dict(orient="records")

    # ------------------------------------------------ exact offline operating curves (ideal user)
    from clear.config import load_config
    cfg = load_config()
    att_keys = set(core[core.attacked & (core.policy == "none:none")].key)
    ben_keys_all = set(core[~core.attacked & (core.policy == "none:none")].key)
    subsets = load_subset_outcomes(att_keys)
    att_calls = core_calls[core_calls.key.isin(att_keys)]
    ben_calls = core_calls[core_calls.key.isin(ben_keys_all)]
    # benign tasks with no tool calls still count (0 dialogs)
    ben_frame = pd.DataFrame({"key": sorted(ben_keys_all)})
    check = tiers_from_features(core_calls, cfg)
    statsout["offline_tier_reproduction"] = float((check == core_calls.tier_clear.to_numpy()).mean())
    curves = []
    variants_off = {"CLEAR": (), "CLEAR, detector-evading attacker": ("iota",),
                    "No provenance": ("tau", "kappa"), "No provenance, detector-evading attacker": ("tau", "kappa", "iota")}
    for name, zero in variants_off.items():
        for scale in [0.25, 0.4, 0.55, 0.7, 0.85, 1.0, 1.25, 1.5, 2.0, 2.5]:
            o = oracle_outcomes(att_calls, ben_calls, subsets, tiers_from_features(att_calls, cfg, scale, zero),
                                tiers_from_features(ben_calls, cfg, scale, zero))
            o["dialogs_benign"] = o["dialogs_benign"] * ben_calls.key.nunique() / len(ben_frame)
            curves.append({"variant": name, "threshold_scale": scale, **o})
    curves = pd.DataFrame(curves)
    curves.to_csv(TAB / "operating_curves.csv", index=False)
    statsout["operating_curves"] = curves.to_dict(orient="records")

    # ------------------------------------------------ per model
    pm = []
    for model, d in core.groupby("model"):
        a = d[d.attacked]
        b = d[~d.attacked]
        get = lambda dd, p, col: dd[dd.policy == p][col].astype(float).mean()  # noqa: E731
        pm.append({"model": model, "n_attacked": int((a.policy == "none:none").sum()),
                   "ASR_none": get(a, "none:none", "s"), "ASR_clear_auto": get(a, "clear:auto", "s"),
                   "ASR_clear_oracle": get(a, "clear:oracle", "s"), "BU_none": get(b, "none:none", "u"),
                   "BU_clear_auto": get(b, "clear:auto", "u"), "dialogs_clear": get(b, "clear:oracle", "confirm"),
                   "dialogs_confirm_all": get(b, "confirm_all:oracle", "confirm")})
    pm = pd.DataFrame(pm)
    pm.to_csv(TAB / "per_model.csv", index=False)
    statsout["per_model_max_asr_clear_oracle"] = float(pm.ASR_clear_oracle.max())

    # ------------------------------------------------ attack-type generalisation (GPT-4o)
    g = ep[(ep.pipeline == "gpt-4o-2024-05-13")]
    at_rows = []
    for atk in ["important_instructions", "tool_knowledge", "ignore_previous", "direct", "injecagent"]:
        d = g[(g.attack == atk)]
        if d.empty:
            continue
        row = {"attack": atk, "n": int((d.policy == "none:none").sum())}
        for p in ["none:none", "pi_detector:auto", "clear_no_injection:oracle", "clear:oracle", "clear:auto"]:
            row[p] = float(d[d.policy == p].s.astype(float).mean())
        at_rows.append(row)
    at = pd.DataFrame(at_rows)
    at.to_csv(TAB / "attack_types.csv", index=False)
    statsout["attack_types"] = at.to_dict(orient="records")

    # ------------------------------------------------ published defences (GPT-4o etc.)
    pub = []
    for pipe, d in ep[ep.attack.isin(["important_instructions", "none"])].groupby("pipeline"):
        if d.defence.iloc[0] == "none" and pipe not in ("gpt-4o-2024-05-13", "meta-llama_Llama-3.3-70B-Instruct",
                                                         "claude-3-sonnet-20240229", "Meta-SecAlign-70B"):
            continue
        a, b = d[d.attacked], d[~d.attacked]
        for p in ["none:none", "clear:oracle", "clear:auto"]:
            pub.append({"pipeline": pipe, "model": d.model.iloc[0], "defence": d.defence.iloc[0], "policy": p,
                        "ASR": float(a[a.policy == p].s.astype(float).mean()),
                        "UA": float(a[a.policy == p].u.astype(float).mean()),
                        "BU": float(b[b.policy == p].u.astype(float).mean()) if len(b) else np.nan,
                        "dialogs_benign": float(b[b.policy == p].confirm.mean()) if len(b) else np.nan,
                        "n_attacked": int((a.policy == p).sum())})
    pub = pd.DataFrame(pub)
    pub.to_csv(TAB / "published_defences.csv", index=False)
    statsout["published_defences"] = pub.to_dict(orient="records")

    # ------------------------------------------------ latency
    lat = calls.latency_ms
    statsout["latency_ms"] = {"median": float(lat.median()), "p95": float(lat.quantile(0.95)),
                              "p99": float(lat.quantile(0.99)), "max": float(lat.max()), "n": int(len(lat))}

    # ------------------------------------------------ human simulation (if available)
    hs_path = ROOT / "results" / "human_sim.csv"
    plt = setup_mpl()
    if hs_path.exists():
        hs = pd.read_csv(hs_path)
        grid = hs[hs.sweep == "grid"]
        cmp = grid.pivot_table(index=["d0", "d_prov", "lam", "a_min", "criterion"], columns="policy", values="e2e_asr")
        cmpd = grid.pivot_table(index=["d0", "d_prov", "lam", "a_min", "criterion"], columns="policy",
                                values="dialogs_per_benign_task")
        statsout["human_sim"] = {
            "default": hs[hs.sweep == "default"].to_dict(orient="records"),
            "grid_points": int(len(cmp)),
            "share_clear_lower_asr_than_confirm_all": float((cmp["clear"] < cmp["confirm_all"]).mean()),
            "share_clear_no_evidence_lower_asr_than_confirm_all": float((cmp["clear_no_evidence"] < cmp["confirm_all"]).mean()),
            "share_clear_no_evidence_lower_asr_when_dprov0": float(
                (cmp.xs(0.0, level="d_prov")["clear_no_evidence"] < cmp.xs(0.0, level="d_prov")["confirm_all"]).mean()),
            "median_asr_clear": float(cmp["clear"].median()), "median_asr_confirm_all": float(cmp["confirm_all"].median()),
            "dialogs_benign_clear": float(cmpd["clear"].median()), "dialogs_benign_confirm_all": float(cmpd["confirm_all"].median()),
        }
        fig_human(hs, plt)

    # ------------------------------------------------ figures
    fig_tradeoff(main, plt)
    fig_per_model(pm, plt)
    fig_roc_plot(core_calls, {"clear": "CLEAR (full)", "clear_no_provenance": "- provenance",
                              "clear_no_injection": "- injection signal", "clear_no_deviation": "- envelope deviation"}, plt)
    fig_tiers(core_calls, plt)
    fig_curves(curves, main, plt)

    # ------------------------------------------------ LaTeX artefacts for the manuscript
    write_paper_tables(statsout, main, pub, at, pm, curves, core)

    with open(ROOT / "results" / "stats.json", "w") as fh:
        json.dump(statsout, fh, indent=2, default=float)
    print(json.dumps({k: statsout[k] for k in ("dataset", "label_agreement", "interruptions_wilcoxon",
                                               "latency_ms")}, indent=2, default=float))
    print(main[["label", "ASR", "UA", "BU", "int_benign", "int_attacked"]].to_string())


if __name__ == "__main__":
    main()
