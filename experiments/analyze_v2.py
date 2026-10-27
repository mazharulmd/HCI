"""Tables, figures and LaTeX macros for the combined-version experiments (E1-E3, audit).

Inputs : results/laundering.csv, results/tables/cross_benchmark.csv,
         results/tables/offline_variants.csv, results/human_sim.csv, results/audit/*.json
Outputs: results/tables/{laundering,cross_benchmark,population}.tex,
         results/tables/numbers_v2.tex, figures/fig_laundering.{pdf,png}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from experiments.analyze import C, GRID, INK, MUTED, setup_mpl  # noqa: E402

TAB, FIG = ROOT / "results" / "tables", ROOT / "figures"
MODES = [("base64", "base64 value"), ("hex", "hex value"), ("homoglyph", "homoglyph value"),
         ("zero_width", "zero-width split"), ("bracket", "value with [at]/[dot]"), ("block_base64", "whole block base64")]


def pct(x, nd=1):
    return "--" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{nd}f}"


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def main() -> None:
    mac = {}
    # ---------------------------------------------------------------- E1 laundering
    d = pd.read_csv(ROOT / "results" / "laundering.csv")
    rows, plot = [], []
    configs = [c for c in ("v1", "v2", "v2.1") if c in set(d.config)]
    for mode, label in MODES:
        keys = set(d[(d["mode"] == mode) & (d.replacements > 0)].key)
        row = [label, str(len(keys))]
        plain = d[(d["mode"] == "plain") & (d.config == "v1") & d.key.isin(keys)]
        row.append(pct(plain.attack_success.mean()))
        for cfg in configs:
            sub = d[(d["mode"] == mode) & (d.config == cfg) & d.key.isin(keys)]
            k, n = int(sub.attack_success.sum()), len(sub)
            lo, hi = wilson(k, n)
            row.append(f"{pct(k / n)} [{pct(lo)}, {pct(hi)}]")
            plot.append({"mode": label, "config": cfg, "asr": k / n, "lo": lo, "hi": hi, "plain": plain.attack_success.mean()})
            cname = {"v1": "Vone", "v2": "Vtwo", "v2.1": "Vtwoone"}[cfg]
            mac[f"laund{mode.replace('_', '').replace('64', 'sixtyfour')}{cname}"] = pct(k / n)
        rows.append(row)
    head = ["Encoding of the attacker's value", "Episodes", "Plain (v1)"] + [f"Laundered, CLEAR {c}" for c in configs]
    lines = [r"\begin{tabular}{l r r " + "r" * len(configs) + "}", r"\toprule", " & ".join(head) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "laundering.tex").write_text("\n".join(lines) + "\n")
    n_succ = d[(d["mode"] == "plain") & (d.config == "v1")].key.nunique()
    mac["laundN"] = f"{n_succ:,}".replace(",", "{,}")
    v1vals = [p["asr"] for p in plot if p["config"] == "v1" and p["mode"] != "whole block base64"]
    v2vals = [p["asr"] for p in plot if p["config"] == "v2" and p["mode"] != "whole block base64"]
    mac["laundVoneMin"], mac["laundVoneMax"] = pct(min(v1vals)), pct(max(v1vals))
    mac["laundVtwoVal"] = pct(max(v2vals), 2)
    mac["laundPlainVal"] = pct([p["plain"] for p in plot if p["mode"] == "base64 value"][0], 2)
    blk = {p["config"]: p["asr"] for p in plot if p["mode"] == "whole block base64"}
    mac["laundBlockVone"], mac["laundBlockVtwo"] = pct(blk["v1"]), pct(blk["v2"])
    if "v2.1" in blk:
        mac["laundBlockVtwoone"] = pct(blk["v2.1"])
    mac["laundBlockPlain"] = pct([p["plain"] for p in plot if p["mode"] == "whole block base64"][0])

    plt = setup_mpl()
    pf = pd.DataFrame(plot)
    fig, ax = plt.subplots(figsize=(6.0, 2.8))
    labels = [m[1] for m in MODES]
    x = np.arange(len(labels))
    w = 0.8 / (len(configs) + 1)
    plain_vals = [pf[(pf["mode"] == lab)].plain.iloc[0] for lab in labels]
    ax.bar(x - 0.4 + w / 2, 100 * np.array(plain_vals), w * 0.92, color=MUTED, label="no laundering (v1)")
    cols = {"v1": C[1], "v2": C[0], "v2.1": C[2]}
    for j, cfg in enumerate(configs):
        sub = pf[pf.config == cfg].set_index("mode").loc[labels]
        ax.bar(x - 0.4 + w * (j + 1.5), 100 * sub.asr, w * 0.92, color=cols[cfg],
               yerr=[100 * (sub.asr - sub.lo), 100 * (sub.hi - sub.asr)], error_kw={"lw": 0.8, "ecolor": INK},
               label=f"laundered, CLEAR {cfg}")
    ax.set_xticks(x, labels, fontsize=7, rotation=12)
    ax.set_ylabel("Residual attack success (%)\nideal user, among successful attacks", fontsize=7.5)
    ax.legend(fontsize=6.5, ncol=2, loc="upper left")
    ax.grid(axis="x", visible=False)
    fig.savefig(FIG / "fig_laundering.pdf")
    fig.savefig(FIG / "fig_laundering.png")
    plt.close(fig)

    # ---------------------------------------------------------------- offline variants (v2.1 on plain traffic)
    ov_path = TAB / "offline_variants.csv"
    if ov_path.exists():
        ov = pd.read_csv(ov_path).set_index("config")
        for cfg, nm in (("clear_default", "Vone"), ("clear_v2", "Vtwo"), ("clear_v2_1", "Vtwoone")):
            if cfg in ov.index:
                mac[f"off{nm}Asr"] = pct(ov.loc[cfg].asr_ideal_user, 2)
                mac[f"off{nm}Dlg"] = f"{ov.loc[cfg].dialogs_per_benign_task:.2f}"
                mac[f"off{nm}Fer"] = pct(ov.loc[cfg].false_escalation_rate)
                mac[f"off{nm}Rec"] = pct(ov.loc[cfg].escalation_recall)

    # ---------------------------------------------------------------- E2 cross-benchmark
    cb = pd.read_csv(TAB / "cross_benchmark.csv").set_index("engine")
    order = ["CLEAR v2", "CLEAR v1", "PROV-Guard (Gemini)", "Trust-Boundary gate (ChatGPT)", "Confirm-all", "Lexical detector"]
    fams = [("DIRECT_OVERRIDE", "Direct"), ("CONTEXT_FRAMING", "Framing"), ("OBFUSCATED_PAYLOAD", "Obfusc."),
            ("CROSS_TOOL_CHAIN", "Chain"), ("GOAL_MIMICRY", "Mimicry")]
    lines = [r"\begin{tabular}{l rrrrr r rr rr}", r"\toprule",
             r" & \multicolumn{6}{c}{PROV-Guard-250: escalation recall (\%)} & \multicolumn{2}{c}{FER benign (\%)} & \multicolumn{2}{c}{Trust-Boundary-8 (\%)}\\",
             r"\cmidrule(lr){2-7}\cmidrule(lr){8-9}\cmidrule(lr){10-11}",
             "Engine & " + " & ".join(f[1] for f in fams) + r" & All & all & high-priv. & recall & FER \\", r"\midrule"]
    for e in order:
        if e not in cb.index:
            continue
        r = cb.loc[e]
        vals = [pct(r[f[0]], 0) for f in fams] + [pct(r["all attacks"], 0), pct(r["FER benign (all)"], 0),
                                                   pct(r["FER benign high-priv."], 0), pct(r.get("TB-8 recall"), 0),
                                                   pct(r.get("TB-8 FER"), 0)]
        lines.append(e.replace("&", r"\&") + " & " + " & ".join(vals) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TAB / "cross_benchmark.tex").write_text("\n".join(lines) + "\n")
    for e, nm in (("CLEAR v2", "Clear"), ("PROV-Guard (Gemini)", "Pg"), ("Trust-Boundary gate (ChatGPT)", "Tb"),
                  ("Confirm-all", "Call"), ("Lexical detector", "Det")):
        mac[f"cb{nm}Fer"] = pct(cb.loc[e, "FER benign high-priv."], 0)
        mac[f"cb{nm}Rec"] = pct(cb.loc[e, "all attacks"], 0)
        mac[f"cb{nm}FerAlt"] = pct(cb.loc[e, "FER high-priv. (internal=untrusted)"], 0)

    # ---------------------------------------------------------------- E3 population heterogeneity
    hs = pd.read_csv(ROOT / "results" / "human_sim.csv")
    pop = hs[hs.sweep == "population"]
    if len(pop):
        names = {"confirm_all": "Confirm-all", "confirm_all_evidence": "Confirm-all + evidence",
                 "clear_no_evidence": "CLEAR selectivity only", "clear": "CLEAR (full)"}
        lines = [r"\begin{tabular}{l rrr}", r"\toprule",
                 r"Interface & balanced & mostly novice & mostly expert \\", r"\midrule"]
        for pol, lab in names.items():
            vals = [pct(pop[(pop.policy == pol) & (pop.population == p)].e2e_asr.iloc[0])
                    for p in ("balanced", "mostly_novice", "mostly_expert")]
            lines.append(lab + " & " + " & ".join(vals) + r" \\")
        lines += [r"\bottomrule", r"\end{tabular}"]
        (TAB / "population.tex").write_text("\n".join(lines) + "\n")
        for p, nm in (("balanced", "Bal"), ("mostly_novice", "Nov"), ("mostly_expert", "Exp")):
            mac[f"pop{nm}Clear"] = pct(pop[(pop.policy == "clear") & (pop.population == p)].e2e_asr.iloc[0])
            mac[f"pop{nm}Call"] = pct(pop[(pop.policy == "confirm_all") & (pop.population == p)].e2e_asr.iloc[0])

    # ---------------------------------------------------------------- audit of the earlier simulation
    a0 = json.load(open(ROOT / "results" / "audit" / "gemini_sim_reported_constants.json"))
    a1 = json.load(open(ROOT / "results" / "audit" / "gemini_sim_neutralised_constants.json"))
    for k, nm in (("PROV_GUARD_FULL", "Full"), ("ABL_NO_CGASD", "NoCgasd"), ("ABL_NO_ICSP", "NoIcsp"),
                  ("ABL_NO_DLPA", "NoDlpa"), ("B3_BINARY_MODAL", "Modal")):
        mac[f"audit{nm}Rep"] = f"{a0[k]['asr_mean']:.1f}"
        mac[f"audit{nm}Neu"] = f"{a1[k]['asr_mean']:.1f}"

    with open(TAB / "numbers_v2.tex", "w") as fh:
        fh.write("% generated by experiments/analyze_v2.py -- do not edit\n")
        for k, v in mac.items():
            fh.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")
    print("\n".join(f"{k} = {v}" for k, v in mac.items()))


if __name__ == "__main__":
    main()
