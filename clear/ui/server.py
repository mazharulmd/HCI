"""Minimal, dependency-free server for the CLEAR interface and user-study apparatus.

    python -m clear.ui.server --port 8765
    open http://localhost:8765/?condition=clear&pid=P001

Conditions (2x2 factorial selectivity x evidence, see docs/user_study/protocol.md):
    clear                 selective escalation + evidence dialogs (full CLEAR)
    clear_generic         selective escalation, generic dialogs
    confirm_all_evidence  every side-effecting action, evidence dialogs
    confirm_all           every side-effecting action, generic dialogs
    none                  no mediation: the agent acts autonomously (audit log only)

Decision events and questionnaire answers are appended to
``user_study_logs/<pid>.jsonl``. No personal data is collected beyond the
pseudonymous participant id entered by the experimenter.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"
LOGS = Path(__file__).resolve().parents[2] / "user_study_logs"
PID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_BODY = 64 * 1024


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC), **kw)

    def log_message(self, fmt, *args):  # quieter console
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        if self.path not in ("/api/log", "/api/questionnaire"):
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
        event["server_time"] = time.time()
        event["kind"] = self.path.rsplit("/", 1)[-1]
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / f"{pid}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event) + "\n")
        return self._json(HTTPStatus.OK, {"ok": True})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CLEAR UI on http://{args.host}:{args.port}/?condition=clear&pid=P001")
    srv.serve_forever()


if __name__ == "__main__":
    main()
