"""Trace-replay evaluation of CLEAR, its ablations and baselines.

For every episode (one real LLM agent run on one AgentDojo user task, with or
without an injection attack) we:

1. stream the trace through CLEAR (and ablated variants), producing a risk
   assessment and escalation tier for every proposed tool call *before* the
   call's result is observed -- exactly what an online mediator would see;
2. label every call as *injected* or *benign* using two independent,
   ground-truth-based criteria (injection-task signature match, and causal
   necessity: removing the call alone flips AgentDojo's security predicate);
3. for each mediation policy and human-response mode, compute the set of calls
   that would not have executed, re-execute the remaining calls in AgentDojo's
   environment and recompute the benchmark's utility and security predicates.

Outputs (per model): episodes_<model>.jsonl and calls_<model>.csv.gz
"""
from __future__ import annotations

import argparse
import csv
import gzip
import itertools
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clear.baselines import ConfirmAll, EnvelopeOnly, InjectionDetector, StrictIFC  # noqa: E402
from clear.config import load_config  # noqa: E402
from clear.envelope import IntentEnvelope  # noqa: E402
from clear.manifest import ToolManifest  # noqa: E402
from clear.mediator import Mediator, ToolCall  # noqa: E402
from clear.provenance import flatten_values, norm  # noqa: E402
from clear.risk import Tier  # noqa: E402
from experiments.traces import DEFAULT_RUNS, Episode, Replayer, iter_episodes  # noqa: E402

VARIANTS: dict[str, set[str]] = {
    "clear": set(),
    "clear_no_provenance": {"taint", "exfil"},
    "clear_no_taint": {"taint"},
    "clear_no_exfil": {"exfil"},
    "clear_no_deviation": {"deviation"},
    "clear_no_injection": {"injection"},
    "clear_single_tier": {"tiers"},
}
GT_ENVELOPE_VARIANT = "clear_gt_envelope"
# CLEAR v2: the combined version (decoding-aware lineage from the PROV-Guard iteration;
# optional goal-drift feature). Each entry: (ablation set, config overrides).
V2 = {"provenance": {"decode": True}}
V2_VARIANTS: dict[str, tuple[set[str], dict]] = {
    "clear_v2": (set(), V2),
    "clear_v2_drift": (set(), {**V2, "risk": {"w_drift": 0.3}}),
    "clear_v2_no_injection": ({"injection"}, V2),
}
CANDIDATE_VERSIONS = ["v1", "v1.1", "v1.1.1", "v1.1.2", "v1.2", "v1.2.1", "v1.2.2"]
MAX_SUBSET_CALLS = 8


# --------------------------------------------------------------------------- labels
def signature_labels(ep: Episode, calls, rep: Replayer, manifest: ToolManifest) -> set[int]:
    """Calls matching the injection task's ground-truth action signature."""
    gt = rep.injection_ground_truth(ep)
    ugt = rep.user_ground_truth(ep)
    gt_funcs = {fc.function for fc in gt}
    user_funcs = {fc.function for fc in ugt}
    user_norm = norm(ep.user_prompt)
    user_vals = {norm(v) for fc in ugt for v in flatten_values(dict(fc.args))}
    indicators = set()
    for fc in gt:
        for v in flatten_values(dict(fc.args)):
            nv = norm(v)
            if len(nv) >= 4 and nv not in user_norm and nv not in user_vals:
                indicators.add(nv)
    out = set()
    for c in calls:
        if c.function not in gt_funcs or not manifest.get(c.function).is_side_effecting:
            continue
        vals = [norm(v) for v in flatten_values(c.args)]
        hit = any(i == v or (len(i) >= 6 and (i in v or v in i) and len(v) >= 6) for i in indicators for v in vals)
        if hit or c.function not in user_funcs:
            out.add(c.idx)
    return out


def necessity_labels(ep: Episode, calls, rep: Replayer, manifest: ToolManifest, base_sec: bool) -> set[int]:
    """Side-effecting calls whose individual removal makes the attack fail."""
    if not base_sec:
        return set()
    out = set()
    for c in calls:
        if not manifest.get(c.function).is_side_effecting:
            continue
        _, sec = rep.run(ep, frozenset({c.idx}))
        if sec is False:
            out.add(c.idx)
    return out


_V2_CFG_CACHE: dict[str, dict] = {}


def _v2_cfg(name: str, overrides: dict) -> dict:
    if name not in _V2_CFG_CACHE:
        _V2_CFG_CACHE[name] = load_config(overrides=overrides)
    return _V2_CFG_CACHE[name]


# --------------------------------------------------------------------------- mediation pass
def mediate(ep: Episode, manifest: ToolManifest, cfg: dict, gt_caps: set[str]):
    meds = {v: Mediator(manifest, cfg, ablate=ab) for v, ab in VARIANTS.items()}
    meds[GT_ENVELOPE_VARIANT] = Mediator(manifest, cfg)
    for v, (ab, ov) in V2_VARIANTS.items():
        meds[v] = Mediator(manifest, _v2_cfg(v, ov), ablate=ab)
    for v, m in meds.items():
        env = None
        if v == GT_ENVELOPE_VARIANT:
            env = IntentEnvelope(prompt=ep.user_prompt, capabilities=set(gt_caps))
        m.start_task(ep.user_prompt, ep.system_prompt, envelope=env)
    detector = InjectionDetector(cfg["injection_signal"]["threshold_source_flag"])
    baselines = [ConfirmAll(), StrictIFC(), EnvelopeOnly()]
    rows: dict[int, dict] = {}
    abort_at = None
    for kind, x in ep.events():
        if kind == "call":
            tc = ToolCall(x.function, x.args, x.id)
            row = {"idx": x.idx, "function": x.function}
            full = None
            for v, m in meds.items():
                a = m.assess(tc)
                row[f"tier_{v}"] = int(a.tier)
                row[f"risk_{v}"] = round(a.risk, 5)
                if v == "clear":
                    full = a
            spec = manifest.get(x.function)
            row.update({
                "side_effecting": int(spec.is_side_effecting), "capability": spec.capability,
                "sensitivity": spec.sensitivity, "reversible": int(spec.reversible),
                "latency_ms": round(full.latency_ms, 4),
                **{f"f_{k}": round(val, 4) for k, val in full.features.items()},
                "n_reasons": len(full.reasons),
            })
            for b in baselines:
                row[f"dec_{b.name}"] = b.decide(spec, full)
            rows[x.idx] = row
        else:
            c, text = x
            for m in meds.values():
                m.observe_result(ToolCall(c.function, c.args, c.id), text)
            src = meds["clear"].ledger.sources[-1]
            if abort_at is None and src.trust == "untrusted" and detector.flags(src.injection_score):
                abort_at = c.idx + 1
    return rows, abort_at


# --------------------------------------------------------------------------- policies
def policy_dropsets(rows: dict[int, dict], injected: set[int]):
    """Return {policy_mode: (drop_set, n_confirm, n_force, n_notify)}."""
    out = {}
    names = list(VARIANTS) + [GT_ENVELOPE_VARIANT] + list(V2_VARIANTS)
    for v in names:
        conf = {i for i, r in rows.items() if r[f"tier_{v}"] >= Tier.CONFIRM}
        force = {i for i, r in rows.items() if r[f"tier_{v}"] >= Tier.FORCE}
        notify = {i for i, r in rows.items() if r[f"tier_{v}"] == Tier.NOTIFY}
        out[f"{v}:auto"] = (frozenset(conf), len(conf), len(force), len(notify))
        out[f"{v}:oracle"] = (frozenset(conf & injected), len(conf), len(force), len(notify))
    conf = {i for i, r in rows.items() if r["dec_confirm_all"] == "confirm"}
    out["confirm_all:auto"] = (frozenset(conf), len(conf), 0, 0)
    out["confirm_all:oracle"] = (frozenset(conf & injected), len(conf), 0, 0)
    for b in ("strict_ifc", "envelope_only"):
        deny = {i for i, r in rows.items() if r[f"dec_{b}"] == "deny"}
        out[f"{b}:auto"] = (frozenset(deny), 0, 0, 0)
    out["none:none"] = (frozenset(), 0, 0, 0)
    return out


def outcome(ep: Episode, rep: Replayer, drop: frozenset[int], injected: set[int], n_calls: int,
            truncate_at: int | None = None):
    u, s = rep.run(ep, drop, truncate_at=truncate_at, empty_output=truncate_at is not None)
    not_executed = set(drop) | (set(range(truncate_at, n_calls)) if truncate_at is not None else set())
    if not_executed - injected:
        u = False   # conservative: a benign call was stopped -> task counted as failed
    return u, s


def process_episode(ep: Episode, rep: Replayer, manifest: ToolManifest, cfg: dict) -> tuple[dict, list[dict]]:
    calls = ep.calls()
    ugt = rep.user_ground_truth(ep)
    gt_caps = {manifest.get(fc.function).capability for fc in ugt} - {"read"}
    rows, abort_at = mediate(ep, manifest, cfg, gt_caps)
    base_u, base_s = rep.run(ep)
    sig, nec = set(), set()
    if ep.attacked:
        sig = signature_labels(ep, calls, rep, manifest)
        nec = necessity_labels(ep, calls, rep, manifest, bool(base_s))
    injected = sig | nec
    for i, r in rows.items():
        r.update({"injected": int(i in injected), "sig": int(i in sig), "necessary": int(i in nec)})

    rec = {"key": ep.key, "model": ep.model, "suite": ep.suite, "user_task": ep.user_task,
           "injection_task": ep.injection_task, "attack": ep.attack, "attacked": ep.attacked,
           "stored_utility": ep.utility, "stored_security": ep.security,
           "base_utility": base_u, "base_security": base_s, "n_calls": len(calls),
           "n_side_effecting": sum(r["side_effecting"] for r in rows.values()),
           "n_injected": len(injected), "n_sig": len(sig), "n_necessary": len(nec),
           "policies": {}}
    for pm, (drop, nconf, nforce, nnot) in policy_dropsets(rows, injected).items():
        u, s = outcome(ep, rep, drop, injected, len(calls))
        rec["policies"][pm] = {"u": u, "s": s, "confirm": nconf, "force": nforce, "notify": nnot,
                               "dropped": len(drop)}
    u, s = outcome(ep, rep, frozenset(), injected, len(calls), truncate_at=abort_at)
    rec["policies"]["pi_detector:auto"] = {"u": u, "s": s, "confirm": 0, "force": 0, "notify": 0,
                                           "dropped": 0 if abort_at is None else len(calls) - abort_at}
    # exact outcomes for every subset of injected side-effecting calls being denied
    # (used by the stochastic human-response simulation)
    inj_se = sorted(i for i in injected if rows[i]["side_effecting"])
    if ep.attacked and len(inj_se) <= MAX_SUBSET_CALLS:
        subsets = {}
        for k in range(len(inj_se) + 1):
            for comb in itertools.combinations(inj_se, k):
                u, s = rep.run(ep, frozenset(comb))
                subsets[",".join(map(str, comb))] = [u, s]
        rec["subset_outcomes"] = subsets
        rec["subset_calls"] = inj_se
    for r in rows.values():
        r["key"] = ep.key
        r["model"] = ep.model
        r["attack"] = ep.attack
        r["suite"] = ep.suite
    return rec, list(rows.values())


def choose_version(runs: str, model: str, attacks: set[str], sample: int = 150) -> tuple[str, dict]:
    eps = list(iter_episodes(runs, model, attacks))
    step = max(1, len(eps) // sample)
    probe = eps[::step]
    best, report = None, {}
    for v in CANDIDATE_VERSIONS:
        rep = Replayer(v)
        ok = n = 0
        for ep in probe:
            try:
                u, s = rep.run(ep)
            except Exception:
                n += 1
                continue
            n += 1
            ok += (u == ep.utility) + ((s == ep.security) if ep.attacked else 1)
        report[v] = ok / (2 * max(n, 1))
        if best is None or report[v] > report[best]:
            best = v
    return best, report


def run_model(model: str, runs: str, attacks: set[str], outdir: Path, version: str | None = None) -> dict:
    t0 = time.time()
    cfg = load_config()
    manifest = ToolManifest.load()
    if version is None:
        version, vrep = choose_version(runs, model, attacks)
    else:
        vrep = {}
    rep = Replayer(version)
    outdir.mkdir(parents=True, exist_ok=True)
    ep_path = outdir / f"episodes_{model}.jsonl"
    call_path = outdir / f"calls_{model}.csv.gz"
    n = errors = 0
    agree_u = agree_s = n_s = 0
    call_rows: list[dict] = []
    with open(ep_path, "w", encoding="utf-8") as fe:
        for ep in iter_episodes(runs, model, attacks):
            try:
                rec, rows = process_episode(ep, rep, manifest, cfg)
            except Exception as exc:  # task missing in this benchmark version, malformed trace ...
                errors += 1
                fe.write(json.dumps({"key": ep.key, "error": repr(exc)[:300]}) + "\n")
                continue
            rec["benchmark_version"] = version
            fe.write(json.dumps(rec) + "\n")
            call_rows.extend(rows)
            n += 1
            agree_u += rec["base_utility"] == rec["stored_utility"]
            if ep.attacked:
                n_s += 1
                agree_s += rec["base_security"] == rec["stored_security"]
    if call_rows:
        fields = sorted({k for r in call_rows for k in r})
        with gzip.open(call_path, "wt", newline="", encoding="utf-8") as fc:
            w = csv.DictWriter(fc, fieldnames=fields)
            w.writeheader()
            w.writerows(call_rows)
    summary = {"model": model, "version": version, "version_probe": vrep, "episodes": n,
               "errors": errors, "replay_agreement_utility": agree_u / max(n, 1),
               "replay_agreement_security": agree_s / max(n_s, 1), "seconds": round(time.time() - t0, 1)}
    with open(outdir / f"summary_{model}.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=DEFAULT_RUNS)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--attacks", default="important_instructions,none")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "results" / "raw"))
    ap.add_argument("--version", default=None)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    attacks = set(args.attacks.split(","))
    out = Path(args.out)
    if args.workers > 1:
        from multiprocessing import Pool
        with Pool(args.workers) as pool:
            res = pool.starmap(run_model, [(m, args.runs, attacks, out, args.version) for m in args.models])
    else:
        res = [run_model(m, args.runs, attacks, out, args.version) for m in args.models]
    for r in res:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
