"""Study apparatus: random assignment, debrief gating, and the pre-registered analysis.

The analysis test runs on SYNTHETIC logs written to a temporary directory. They
exercise the code only and are never written to results/.
"""
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from clear.ui import server as ui

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "clear" / "ui" / "static"


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "LOGS", tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def call(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def test_allocation_is_block_balanced():
    a = ui.make_allocation(seed=1)
    for stratum in ui.STRATA:
        seq = a["sequences"][stratum]
        assert set(seq) == set(ui.STUDY_CONDITIONS)
        # every block is balanced, so the counts never drift apart by more than one block's surplus
        for n in range(8, 220, 8):
            c = Counter(seq[:n])
            assert max(c.values()) - min(c.values()) <= 2


def test_assignment_is_persistent_and_concealed(srv):
    base, logs = srv
    s1, r1 = call(f"{base}/api/assign", {"pid": "P001", "stratum": "low"})
    s2, r2 = call(f"{base}/api/assign", {"pid": "P001", "stratum": "low"})
    assert s1 == s2 == 200 and r1["condition"] == r2["condition"] and r2["resumed"]
    assert r1["condition"] in ui.STUDY_CONDITIONS
    assert call(f"{base}/api/assign", {"pid": "P002", "stratum": "medium"})[0] == 400
    # the allocation sequence and the answer key are never served
    for path in ("/allocation.json", "/assignments.json", "/../user_study_logs/allocation.json",
                 "/data/ui_answer_key.json", "/../../data/ui_answer_key.json"):
        assert call(base + path)[0] == 404
    assert (logs / "allocation.json").exists()
    # events are stamped with the server-side assignment
    call(f"{base}/api/log", {"pid": "P001", "type": "decision", "condition": "confirm_all"})
    last = json.loads((logs / "P001.jsonl").read_text().splitlines()[-1])
    assert last["assigned_condition"] == r1["condition"]
    st, status = call(f"{base}/api/status")
    assert st == 200 and status["assigned"] == 1 and "condition" not in status["participants"][0]


def test_debrief_only_after_questionnaire(srv):
    base, _ = srv
    assert call(f"{base}/api/debrief?pid=P009")[0] == 403
    call(f"{base}/api/questionnaire", {"pid": "P009", "answers": {}})
    st, res = call(f"{base}/api/debrief?pid=P009")
    assert st == 200 and len(res["attacked_tasks"]) == 4


def test_practice_tasks_are_separate_and_unlabelled():
    data = json.loads((STATIC / "scenarios.json").read_text())
    key = json.loads((ROOT / "data" / "ui_answer_key.json").read_text())
    assert len(data["scenarios"]) == 16 and len(data["practice"]) == 2
    assert all(key[p["id"]].get("practice") for p in data["practice"])
    assert {p["id"] for p in data["practice"]}.isdisjoint(s["id"] for s in data["scenarios"])
    for sc in data["practice"]:
        assert "attacked" not in sc and "injected_calls" not in sc


def _synthetic_session(pid, cond, rng, data, key, attention_ok=True, minutes=20.0):
    """Synthetic event stream in the server's log format (test data only)."""
    sel = cond in ("clear", "clear_generic")
    ev = [{"pid": pid, "type": "consent", "agreed": True, "kind": "log"},
          {"pid": pid, "type": "demographics", "answers": {"programming": "little"}, "kind": "log"},
          {"pid": pid, "type": "assignment", "condition": cond, "kind": "log"}]
    t0, step = 1_000_000, minutes * 60000 / 16
    p_deny_inj = {"clear": 0.9, "clear_generic": 0.6, "confirm_all_evidence": 0.6, "confirm_all": 0.3}[cond]
    for i, sc in enumerate(data["scenarios"]):
        base = {"pid": pid, "condition": cond, "scenario": sc["id"], "phase": "main", "kind": "log"}
        ev.append({**base, "type": "scenario_start", "t": t0 + i * step})
        for st in sc["steps"]:
            if st["type"] != "call":
                continue
            shown = st["tier"] in ("CONFIRM", "FORCE") if sel else st["side_effecting"]
            if shown:
                inj = st["idx"] in key[sc["id"]]["injected_calls"]
                deny = rng.random() < (p_deny_inj if inj else 0.05)
                ev.append({**base, "type": "decision", "call_idx": st["idx"], "tier": st["tier"],
                           "approve": not deny, "rt_ms": 4000, "t": t0 + i * step + 1000})
        ev.append({**base, "type": "scenario_end", "t": t0 + (i + 1) * step - 1})
        if i + 1 in (5, 11):
            check = "AC1" if i + 1 == 5 else "AC2"
            ev.append({**base, "scenario": None, "type": "attention_check", "check": check, "correct": attention_ok})
    answers = {**{f"sus_{i}": 3 for i in range(1, 11)}, **{f"trust_{i}": 4 for i in range(1, 13)},
               **{f"tlx_{k}": 40 for k in ("mental", "physical", "temporal", "performance", "effort", "frustration")}}
    ev.append({"pid": pid, "condition": cond, "answers": answers, "kind": "questionnaire"})
    return ev


def test_analysis_runs_on_synthetic_logs(tmp_path):
    data = json.loads((STATIC / "scenarios.json").read_text())
    key = json.loads((ROOT / "data" / "ui_answer_key.json").read_text())
    rng = np.random.default_rng(0)
    assignments = {}
    for j, cond in enumerate(ui.STUDY_CONDITIONS * 10):
        pid = f"S{j:03d}"
        ev = _synthetic_session(pid, cond, rng, data, key, attention_ok=(pid != "S000"))
        if pid == "S002":   # an aborted first attempt with all calls denied, then a full restart
            aborted = [{**e, "approve": False} if e.get("type") == "decision" else e for e in ev[:20]]
            ev = aborted + ev
        assignments[pid] = {"condition": cond, "stratum": "low"}
        (tmp_path / f"{pid}.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    (tmp_path / "PILOT01.jsonl").write_text(json.dumps({"pid": "PILOT01", "type": "consent", "agreed": True}))
    (tmp_path / "assignments.json").write_text(json.dumps(assignments))
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(ROOT / "experiments" / "analyze_user_study.py"), "--logs", str(tmp_path),
                    "--out", str(out)], check=True, capture_output=True)
    parts = pd.read_csv(out / "participants.csv").set_index("pid")
    assert "PILOT01" not in parts.index
    assert parts.loc["S000", "excluded"] == "failed both attention checks"
    assert (parts.excluded.fillna("") == "").sum() == 39
    assert parts.loc["S002", "restarts"] == 1 and parts.loc["S002", "tasks_completed"] == 16
    # prevention recomputed by hand for one participant
    trials = pd.read_csv(out / "trials.csv")
    ev = [json.loads(x) for x in (tmp_path / "S001.jsonl").read_text().splitlines()]
    denied = {(e["scenario"], e["call_idx"]) for e in ev if e.get("type") == "decision" and not e["approve"]}
    expect = np.mean([all((sid, i) in denied for i in k["injected_calls"])
                      for sid, k in key.items() if k["attacked"] and not k.get("practice")])
    assert trials[(trials.pid == "S001") & trials.attacked].prevented.mean() == pytest.approx(expect)
    summary = json.loads((out / "summary.json").read_text())
    gee = {r["effect"]: r for r in summary["primary_gee"]}
    # the synthetic users deny injected calls more often with selectivity and with evidence
    assert gee["selectivity (H-U1)"]["odds_ratio"] > 1 and gee["evidence (H-U2)"]["odds_ratio"] > 1
    assert all(np.isfinite(gee[e]["p_holm"]) for e in ("selectivity (H-U1)", "evidence (H-U2)"))
    assert all(0 < r["p_perm"] <= 1 for r in summary["primary_permutation"])
    assert len(summary["noninferiority"]) == 2
    assert {r["variant"] for r in summary["robustness_gee"]} == {"passed both attention checks",
                                                                 "first attacked task excluded"}
