"""Minimal, dependency-free server for the CLEAR interface and user-study apparatus.

    python -m clear.ui.server --port 8765                  # demo on this computer
    python -m clear.ui.server --host 0.0.0.0 --port 8765   # lab: serve the lab network

Demo: open http://localhost:8765/?condition=clear&pid=P001
Study: open http://<server>:8765/start.html on each lab computer
(see docs/user_study/lab_runbook.md).

Conditions (2x2 factorial selectivity x evidence, see docs/user_study/protocol.md):
    clear                 selective escalation + evidence dialogs (full CLEAR)
    clear_generic         selective escalation, generic dialogs
    confirm_all_evidence  every side-effecting action, evidence dialogs
    confirm_all           every side-effecting action, generic dialogs
    none                  no mediation: the agent acts autonomously (demo only, never assigned)

Study participants are assigned by the server: stratified (programming
experience) permuted-block randomisation. The allocation sequence is generated
once, from a random seed, and kept in ``user_study_logs/allocation.json``, which
is never served. Decision events, questionnaire answers and assignments are
appended to ``user_study_logs/``. No personal data is collected beyond the
pseudonymous participant id entered by the experimenter.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import secrets
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

STATIC = Path(__file__).resolve().parent / "static"
ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "user_study_logs"
ANSWER_KEY = ROOT / "data" / "ui_answer_key.json"
PID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_BODY = 64 * 1024

STUDY_CONDITIONS = ("clear", "confirm_all", "clear_generic", "confirm_all_evidence")
STRATA = ("low", "high")          # self-reported programming experience
BLOCK_SIZES = (4, 8)              # mixed block sizes keep the next allocation unpredictable
SEQUENCE_LEN = 400                # per stratum; far more than the planned N = 220
_lock = threading.Lock()


def _write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    tmp.replace(path)


def make_allocation(seed: int) -> dict:
    """Permuted blocks of 4 or 8 (each condition equally often per block), per stratum."""
    rng = random.Random(seed)
    seqs = {}
    for stratum in STRATA:
        seq = []
        while len(seq) < SEQUENCE_LEN:
            block = list(STUDY_CONDITIONS) * (rng.choice(BLOCK_SIZES) // len(STUDY_CONDITIONS))
            rng.shuffle(block)
            seq += block
        seqs[stratum] = seq
    return {"seed": seed, "created": time.time(), "sequences": seqs, "next": {s: 0 for s in STRATA}}


def _allocation() -> dict:
    path = LOGS / "allocation.json"
    if not path.exists():
        _write_json(path, make_allocation(secrets.randbits(63)))
    return json.loads(path.read_text())


def _assignments() -> dict:
    path = LOGS / "assignments.json"
    return json.loads(path.read_text()) if path.exists() else {}


def assign(pid: str, stratum: str) -> dict:
    """Return the participant's condition, allocating the next one in their stratum if new."""
    with _lock:
        LOGS.mkdir(exist_ok=True)
        done = _assignments()
        if pid in done:
            return {**done[pid], "resumed": True}
        alloc = _allocation()
        i = alloc["next"][stratum]
        rec = {"condition": alloc["sequences"][stratum][i], "stratum": stratum, "slot": i, "time": time.time()}
        alloc["next"][stratum] = i + 1
        done[pid] = rec
        _write_json(LOGS / "allocation.json", alloc)
        _write_json(LOGS / "assignments.json", done)
        return {**rec, "resumed": False}


def _events(pid: str) -> list[dict]:
    path = LOGS / f"{pid}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def attacked_task_prompts() -> list[str]:
    key = json.loads(ANSWER_KEY.read_text())
    data = json.loads((STATIC / "scenarios.json").read_text())
    return [sc["prompt"] for sc in data["scenarios"] if key.get(sc["id"], {}).get("attacked")]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC), **kw)

    def log_message(self, fmt, *args):  # quieter console
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):  # study pages must never be served stale from a lab browser's cache
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):  # noqa: N802
        url = urlparse(self.path)
        if url.path == "/api/debrief":
            pid = (parse_qs(url.query).get("pid") or [""])[0]
            if not PID_RE.match(pid):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad pid"})
            # the attacked tasks are revealed only once this participant has submitted the questionnaire
            if not any(e.get("kind") == "questionnaire" for e in _events(pid)):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "questionnaire not submitted"})
            return self._json(HTTPStatus.OK, {"attacked_tasks": attacked_task_prompts()})
        if url.path == "/api/status":
            if self.client_address[0] not in ("127.0.0.1", "::1"):
                return self._json(HTTPStatus.FORBIDDEN, {"error": "status is only available on the server computer"})
            done = _assignments()
            counts = {s: {c: 0 for c in STUDY_CONDITIONS} for s in STRATA}
            rows = []
            for pid, rec in sorted(done.items(), key=lambda kv: kv[1]["time"]):
                counts[rec["stratum"]][rec["condition"]] += 1
                ev = _events(pid)
                rows.append({"pid": pid, "stratum": rec["stratum"],
                             "tasks_done": sum(e.get("type") == "scenario_end" and e.get("phase") == "main" for e in ev),
                             "questionnaire": any(e.get("kind") == "questionnaire" for e in ev)})
            # conditions are not listed per participant, so the experimenter stays blind
            return self._json(HTTPStatus.OK, {"assigned": len(done), "per_stratum_and_condition": counts,
                                              "participants": rows})
        if url.path.startswith("/api/"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        if self.path not in ("/api/log", "/api/questionnaire", "/api/assign"):
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BODY:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad length"})
        try:
            event = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad json"})
        pid = str(event.get("pid", ""))
        if not PID_RE.match(pid):
            return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad pid"})
        if self.path == "/api/assign":
            stratum = event.get("stratum")
            if stratum not in STRATA:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "bad stratum"})
            rec = assign(pid, stratum)
            self._append(pid, {"pid": pid, "type": "assignment", "condition": rec["condition"],
                               "stratum": stratum, "resumed": rec["resumed"]}, "log")
            return self._json(HTTPStatus.OK, {"condition": rec["condition"], "resumed": rec["resumed"]})
        self._append(pid, event, self.path.rsplit("/", 1)[-1])
        return self._json(HTTPStatus.OK, {"ok": True})

    def _append(self, pid: str, event: dict, kind: str) -> None:
        event["server_time"] = time.time()
        event["kind"] = kind
        with _lock:
            LOGS.mkdir(exist_ok=True)
            # stamp the server-side assignment, so a hand-edited condition in the URL is detectable
            event["assigned_condition"] = _assignments().get(pid, {}).get("condition")
            with open(LOGS / f"{pid}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to serve the lab network")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CLEAR UI on http://{args.host}:{args.port}/  (study: /start.html, demo: /?condition=clear&pid=P001)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
