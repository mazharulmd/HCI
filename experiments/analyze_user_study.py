"""Pre-registered analysis of the lab user study (docs/user_study/protocol.md, section 7).

Written before any participant data existed. Reads the logs written by
clear/ui/server.py and the answer key, and writes per-participant, per-trial and
per-dialog tables plus the confirmatory tests:

    python experiments/analyze_user_study.py --logs user_study_logs --out results/user_study

Participant codes starting with PILOT or TEST are pilot or test sessions; they are
listed but never analysed.

Outcomes (protocol section 6)
  * prevented (each attacked task): every injected call was denied in a dialog;
    an injected call never shown in a dialog was executed, so it counts as not prevented
  * benign_ok (each benign task): no benign side-effecting call was denied
  * dialog level: a denial is correct for an injected call, an approval for a benign one;
    SDT d' and c per participant with the log-linear correction

Exclusions (pre-registered): no consent; fewer than all 16 tasks logged (technical
failure); both attention checks failed; tasks completed in under 4 minutes; the
condition in the browser differs from the server's assignment.

Confirmatory tests, in a fixed sequence (each is confirmatory only if all earlier ones
are supported; this controls the familywise error at alpha = .05 without adjustment).
The design was revised before data collection after the power analysis
(docs/user_study/power_analysis.md):
  1. H-U2, evidence improves prevention: logistic GEE (exchangeable working correlation,
     clusters = participants) prevented ~ selective * evidence + C(scenario), effect-coded
     factors (+-0.5), so exp(beta) is the odds ratio between factor levels; two-sided p < .05
     with odds ratio > 1.
  2. H-U1, selectivity does not reduce prevention: participant-level prevention rate,
     selective (A, C) minus non-selective (B, D); non-inferior if the lower bound of the
     90% CI (Welch) is above -10 percentage points.
  3. H-U3a, benign completion of full CLEAR (A) is non-inferior to confirm-all (B):
     lower bound of the 90% CI of A - B above -5 percentage points.
  4. H-U3b, workload of A is non-inferior to B: upper bound of the 90% CI of the NASA-TLX
     difference A - B below +8 points.
Exploratory and robustness: the selectivity superiority effect and the interaction from
the GEE; a stratified permutation test of both main effects on participant-level
prevention rates (valid under separation); the GEE repeated without participants who
failed either attention check and without each participant's first attacked task.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "clear" / "ui" / "static"
CONDITIONS = {  # condition -> (selective, evidence), see protocol section 3
    "clear": (1, 1), "confirm_all": (0, 0), "clear_generic": (1, 0), "confirm_all_evidence": (0, 1)}
LABEL = {"clear": "A full CLEAR", "confirm_all": "B confirm-all", "clear_generic": "C selectivity only",
         "confirm_all_evidence": "D evidence only"}
PILOT_PREFIXES = ("PILOT", "TEST")
MIN_MINUTES = 4.0
NI_MARGIN_SELECTIVITY = 0.10
NI_MARGIN_BENIGN = 0.05
NI_MARGIN_TLX = 8.0
ALPHA = 0.05


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj.tolist()


def load_design(key_path: Path, scen_path: Path) -> dict:
    key = json.loads(key_path.read_text())
    data = json.loads(scen_path.read_text())
    design = {}
    for sc in data["scenarios"]:
        k = key[sc["id"]]
        side = {st["idx"] for st in sc["steps"] if st["type"] == "call" and st["side_effecting"]}
        design[sc["id"]] = {"attacked": bool(k["attacked"]), "injected": set(k["injected_calls"]), "side": side}
    return design


def sus_score(a: dict) -> float:
    items = [int(a[f"sus_{i}"]) for i in range(1, 11)]
    return 2.5 * sum((x - 1) if i % 2 == 0 else (5 - x) for i, x in enumerate(items))


def tlx_raw(a: dict) -> float:
    return float(np.mean([float(a[f"tlx_{k}"]) for k in ("mental", "physical", "temporal", "performance",
                                                            "effort", "frustration")]))


def trust_score(a: dict) -> float:
    # Jian et al. (2000): items 1-5 are distrust items and are reverse-scored on the 1-7 scale
    vals = [int(a[f"trust_{i}"]) for i in range(1, 13)]
    return float(np.mean([8 - v if i < 5 else v for i, v in enumerate(vals)]))


def sdt(hits: int, n_inj: int, fas: int, n_ben: int) -> tuple[float, float]:
    h = (hits + 0.5) / (n_inj + 1)
    f = (fas + 0.5) / (n_ben + 1)
    zh, zf = stats.norm.ppf(h), stats.norm.ppf(f)
    return float(zh - zf), float(-(zh + zf) / 2)


def participant(pid: str, events: list[dict], assigned: dict, design: dict) -> tuple[dict, list[dict], list[dict]]:
    # a restarted session (same code entered again) is re-assigned the same condition;
    # only the last attempt, after the final assignment event, is analysed
    last = max((i for i, e in enumerate(events) if e.get("type") == "assignment"), default=0)
    restarts = sum(e.get("type") == "assignment" for e in events) - 1
    main = [e for e in events[last:] if e.get("phase") == "main"]
    cond = assigned.get("condition")
    consent = [e for e in events if e.get("type") == "consent"]
    demo = next((e["answers"] for e in events if e.get("type") == "demographics"), {})
    quest = next((e["answers"] for e in events if e.get("kind") == "questionnaire"), None)
    ended = {e["scenario"] for e in main if e.get("type") == "scenario_end"}
    shown_at = {}
    for e in main:   # presentation order of the tasks
        if e.get("type") == "scenario_start" and e.get("scenario") not in shown_at:
            shown_at[e["scenario"]] = len(shown_at)
    starts = [e["t"] for e in main if e.get("type") == "scenario_start"]
    ends = [e["t"] for e in main if e.get("type") == "scenario_end"]
    minutes = (max(ends) - min(starts)) / 60000 if starts and ends else np.nan
    att = {e["check"]: bool(e["correct"]) for e in main if e.get("type") == "attention_check"}
    mismatch = any(e.get("condition") and cond and e["condition"] != cond for e in events if e.get("kind") == "log")

    decisions = defaultdict(dict)
    dialogs = []
    for e in main:
        if e.get("type") != "decision" or e.get("scenario") not in design:
            continue
        d = design[e["scenario"]]
        injected = e["call_idx"] in d["injected"]
        decisions[e["scenario"]][e["call_idx"]] = bool(e["approve"])
        dialogs.append({"pid": pid, "scenario": e["scenario"], "call_idx": e["call_idx"], "injected": injected,
                        "approve": bool(e["approve"]), "correct": (not e["approve"]) if injected else bool(e["approve"]),
                        "tier": e.get("tier"), "rt_ms": e.get("rt_ms"), "forced_correct": e.get("forced_correct")})
    trials = []
    for sid, d in design.items():
        if sid not in ended:
            continue
        dec = decisions.get(sid, {})
        row = {"pid": pid, "scenario": sid, "attacked": d["attacked"], "position": shown_at.get(sid)}
        if d["attacked"]:
            row["prevented"] = int(all(dec.get(i) is False for i in d["injected"]))
        else:
            row["benign_ok"] = int(not any(dec.get(i) is False for i in d["side"] - d["injected"]))
        trials.append(row)

    dl = pd.DataFrame(dialogs)
    inj = dl[dl.injected] if len(dl) else dl
    ben = dl[~dl.injected] if len(dl) else dl
    dprime, crit = sdt(int((~inj.approve).sum()) if len(inj) else 0, len(inj),
                       int((~ben.approve).sum()) if len(ben) else 0, len(ben))
    forced = [x for x in (dl.forced_correct if len(dl) else []) if x is not None and not pd.isna(x)]
    tr = pd.DataFrame(trials)
    p = {
        "pid": pid, "condition": cond, "stratum": assigned.get("stratum"),
        "consent": bool(consent) and bool(consent[-1].get("agreed")),
        "programming": demo.get("programming"), "age": demo.get("age"), "gender": demo.get("gender"),
        "security_training": demo.get("security_training"), "ai_use": demo.get("ai_use"),
        "tasks_completed": len(ended & set(design)), "minutes": minutes, "restarts": max(restarts, 0),
        "attention_correct": sum(att.values()), "attention_n": len(att), "condition_mismatch": mismatch,
        "prevention_rate": tr.prevented.mean() if "prevented" in tr else np.nan,
        "benign_completion": tr.benign_ok.mean() if "benign_ok" in tr else np.nan,
        "dialogs": len(dl), "dialog_accuracy": dl.correct.mean() if len(dl) else np.nan,
        "dprime": dprime if len(dl) else np.nan, "criterion": crit if len(dl) else np.nan,
        "median_rt_s": float(dl.rt_ms.median() / 1000) if len(dl) else np.nan,
        "forcing_accuracy": float(np.mean(forced)) if forced else np.nan,
        "envelope_edits": sum(e.get("type") == "envelope_edit" for e in main),
        "undos": sum(e.get("type") == "undo" for e in main),
        "sus": sus_score(quest) if quest else np.nan, "tlx_raw": tlx_raw(quest) if quest else np.nan,
        "trust": trust_score(quest) if quest else np.nan,
    }
    reasons = []
    if not p["consent"]:
        reasons.append("no consent")
    if p["tasks_completed"] < len(design):
        reasons.append("incomplete")
    if p["attention_n"] == 2 and p["attention_correct"] == 0:
        reasons.append("failed both attention checks")
    if not np.isnan(minutes) and minutes < MIN_MINUTES:
        reasons.append(f"under {MIN_MINUTES:g} minutes")
    if mismatch:
        reasons.append("condition mismatch")
    if cond not in CONDITIONS:
        reasons.append("no study assignment")
    p["excluded"] = "; ".join(reasons)
    return p, trials, dialogs


def gee_main_effects(trials: pd.DataFrame) -> pd.DataFrame:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    d = trials[trials.attacked].copy()
    d["sel"] = d.condition.map(lambda c: CONDITIONS[c][0] - 0.5)
    d["ev"] = d.condition.map(lambda c: CONDITIONS[c][1] - 0.5)
    rows = []
    try:
        res = smf.gee("prevented ~ sel * ev + C(scenario)", groups="pid", data=d,
                      family=sm.families.Binomial(), cov_struct=sm.cov_struct.Exchangeable()).fit()
        ci = res.conf_int()
        for term, name in (("sel", "selectivity"), ("ev", "evidence"), ("sel:ev", "interaction")):
            rows.append({"effect": name, "odds_ratio": float(np.exp(res.params[term])),
                         "ci_lo": float(np.exp(ci.loc[term, 0])), "ci_hi": float(np.exp(ci.loc[term, 1])),
                         "z": float(res.tvalues[term]), "p": float(res.pvalues[term])})
    except Exception as exc:  # e.g. perfect separation; the permutation test still applies
        rows = [{"effect": n, "odds_ratio": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "z": np.nan, "p": np.nan,
                 "note": f"GEE not estimable: {exc.__class__.__name__}"}
                for n in ("selectivity", "evidence", "interaction")]
    return pd.DataFrame(rows)


def permutation_main_effects(parts: pd.DataFrame, n_perm: int = 10_000, seed: int = 20261109) -> pd.DataFrame:
    """Difference in mean participant prevention rate between factor levels; labels permuted within strata."""
    rng = np.random.default_rng(seed)
    d = parts.dropna(subset=["prevention_rate"]).reset_index(drop=True)
    y = d.prevention_rate.to_numpy()
    rows = []
    for idx, name in ((0, "selectivity"), (1, "evidence")):
        lab = d.condition.map(lambda c: CONDITIONS[c][idx]).to_numpy()
        obs = y[lab == 1].mean() - y[lab == 0].mean()
        strata = d.stratum.fillna("all").to_numpy()
        cnt = 0
        for _ in range(n_perm):
            perm = lab.copy()
            for s in np.unique(strata):
                m = strata == s
                perm[m] = rng.permutation(perm[m])
            cnt += abs(y[perm == 1].mean() - y[perm == 0].mean()) >= abs(obs) - 1e-12
        rows.append({"effect": name, "diff_prevention": float(obs), "p_perm": (cnt + 1) / (n_perm + 1)})
    out = pd.DataFrame(rows)
    out["p_perm_holm"] = holm(out.p_perm.tolist())
    return out


def welch_noninferiority(x, y, margin: float, worse: str) -> dict:
    """x - y with a 90% Welch CI. worse="lower": non-inferior if the lower bound > -margin;
    worse="higher": non-inferior if the upper bound < +margin. p is the one-sided test of the margin."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    x, y = x[~np.isnan(x)], y[~np.isnan(y)]
    if len(x) < 2 or len(y) < 2:
        return {"diff": np.nan, "ci90_lo": np.nan, "ci90_hi": np.nan, "p": np.nan, "supported": False,
                "note": "too few participants"}
    diff = x.mean() - y.mean()
    vx, vy = x.var(ddof=1) / len(x), y.var(ddof=1) / len(y)
    se = np.sqrt(vx + vy)
    if se == 0:
        ok = diff > -margin if worse == "lower" else diff < margin
        return {"diff": diff, "ci90_lo": diff, "ci90_hi": diff, "p": 0.0 if ok else 1.0, "supported": bool(ok)}
    df = (vx + vy) ** 2 / (vx ** 2 / (len(x) - 1) + vy ** 2 / (len(y) - 1))
    tcrit = stats.t.ppf(0.95, df)
    lo, hi = diff - tcrit * se, diff + tcrit * se
    t = (diff + margin) / se if worse == "lower" else (margin - diff) / se
    return {"diff": diff, "ci90_lo": lo, "ci90_hi": hi, "p": float(stats.t.sf(t, df)),
            "supported": bool(lo > -margin if worse == "lower" else hi < margin)}


def confirmatory(parts: pd.DataFrame, trials: pd.DataFrame, gee: pd.DataFrame | None = None) -> pd.DataFrame:
    """The four confirmatory tests in their fixed sequence (see module docstring)."""
    gee = gee_main_effects(trials) if gee is None else gee
    ev = gee.set_index("effect").loc["evidence"]
    sel = parts.condition.map(lambda c: CONDITIONS[c][0])
    a, b = parts[parts.condition == "clear"], parts[parts.condition == "confirm_all"]
    rows = [{"hypothesis": "H-U2 evidence improves prevention", "estimate": ev.odds_ratio,
             "ci_lo": ev.ci_lo, "ci_hi": ev.ci_hi, "p": ev.p, "criterion": "GEE odds ratio > 1, p < .05",
             "supported": bool(ev.p < ALPHA and ev.odds_ratio > 1) if pd.notna(ev.p) else False}]
    for name, x, y, margin, worse, crit in (
            ("H-U1 selectivity does not reduce prevention", parts[sel == 1].prevention_rate,
             parts[sel == 0].prevention_rate, NI_MARGIN_SELECTIVITY, "lower", "90% CI lower bound > -10 pp"),
            ("H-U3a benign completion A non-inferior to B", a.benign_completion, b.benign_completion,
             NI_MARGIN_BENIGN, "lower", "90% CI lower bound > -5 pp"),
            ("H-U3b workload A non-inferior to B", a.tlx_raw, b.tlx_raw, NI_MARGIN_TLX, "higher",
             "90% CI upper bound < +8 TLX points")):
        r = welch_noninferiority(x, y, margin, worse)
        rows.append({"hypothesis": name, "estimate": r["diff"], "ci_lo": r["ci90_lo"], "ci_hi": r["ci90_hi"],
                     "p": r["p"], "criterion": crit, "supported": r["supported"]})
    out = pd.DataFrame(rows)
    out["confirmatory"] = out.supported.shift(1, fill_value=True).cummin().astype(bool)   # fixed-sequence gate
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default=str(ROOT / "user_study_logs"))
    ap.add_argument("--out", default=str(ROOT / "results" / "user_study"))
    ap.add_argument("--key", default=str(ROOT / "data" / "ui_answer_key.json"))
    ap.add_argument("--scenarios", default=str(STATIC / "scenarios.json"))
    args = ap.parse_args()
    logs, out = Path(args.logs), Path(args.out)
    design = load_design(Path(args.key), Path(args.scenarios))
    assignments = json.loads((logs / "assignments.json").read_text()) if (logs / "assignments.json").exists() else {}
    parts, trials, dialogs, pilots = [], [], [], []
    for f in sorted(logs.glob("*.jsonl")):
        pid = f.stem
        if pid.upper().startswith(PILOT_PREFIXES):
            pilots.append(pid)
            continue
        events = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        p, t, d = participant(pid, events, assignments.get(pid, {}), design)
        parts.append(p)
        trials += [{**r, "condition": p["condition"]} for r in t]
        dialogs += [{**r, "condition": p["condition"]} for r in d]
    if not parts:
        sys.exit(f"no participant logs in {logs} (pilot/test sessions skipped: {len(pilots)})")
    P = pd.DataFrame(parts)
    T, D = pd.DataFrame(trials), pd.DataFrame(dialogs)
    out.mkdir(parents=True, exist_ok=True)
    P.to_csv(out / "participants.csv", index=False)
    T.to_csv(out / "trials.csv", index=False)
    D.to_csv(out / "dialogs.csv", index=False)

    inc = P[P.excluded == ""]
    Ti = T[T.pid.isin(inc.pid)]
    desc = inc.groupby("condition").agg(
        n=("pid", "size"), prevention=("prevention_rate", "mean"), benign_completion=("benign_completion", "mean"),
        dialogs=("dialogs", "mean"), dialog_accuracy=("dialog_accuracy", "mean"), dprime=("dprime", "mean"),
        criterion=("criterion", "mean"), median_rt_s=("median_rt_s", "median"), sus=("sus", "mean"),
        tlx_raw=("tlx_raw", "mean"), trust=("trust", "mean"), forcing_accuracy=("forcing_accuracy", "mean"),
    ).reset_index()
    desc.insert(1, "label", desc.condition.map(LABEL))
    desc.to_csv(out / "descriptives.csv", index=False)
    summary = {
        "n_logged": len(P), "n_included": len(inc), "pilot_sessions_skipped": pilots,
        "exclusions": P[P.excluded != ""][["pid", "excluded"]].to_dict(orient="records"),
        "per_condition": desc.to_dict(orient="records"),
    }
    if inc.condition.nunique() == len(CONDITIONS) and len(Ti):
        g = gee_main_effects(Ti)
        perm = permutation_main_effects(inc)
        conf = confirmatory(inc, Ti, g)
        conf.to_csv(out / "confirmatory.csv", index=False)
        g.to_csv(out / "gee.csv", index=False)
        att_ok = inc[(inc.attention_n < 2) | (inc.attention_correct == inc.attention_n)].pid
        first = Ti[Ti.attacked].sort_values("position").groupby("pid").head(1).index
        rob = pd.concat([gee_main_effects(Ti[Ti.pid.isin(att_ok)]).assign(variant="passed both attention checks"),
                         gee_main_effects(Ti.drop(index=first)).assign(variant="first attacked task excluded")])
        rob.to_csv(out / "robustness_gee.csv", index=False)
        summary["robustness_gee"] = rob.to_dict(orient="records")
        perm.to_csv(out / "permutation.csv", index=False)
        summary.update({"confirmatory": conf.to_dict(orient="records"), "gee": g.to_dict(orient="records"),
                        "permutation": perm.to_dict(orient="records")})
        print(conf.to_string(index=False)); print(g.to_string(index=False)); print(perm.to_string(index=False))
    else:
        summary["note"] = "confirmatory tests need included participants in all four conditions"
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(desc.to_string(index=False))
    print(f"{len(inc)} of {len(P)} participants included; {len(pilots)} pilot/test sessions skipped -> {out}")


if __name__ == "__main__":
    main()
