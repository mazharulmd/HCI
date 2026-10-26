import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from clear.ui import server as ui

STATIC = Path(ui.__file__).resolve().parent / "static"


def test_scenarios_do_not_leak_labels():
    raw = (STATIC / "scenarios.json").read_text()
    data = json.loads(raw)
    assert data["scenarios"] and "config" in data
    for sc in data["scenarios"]:
        assert "attacked" not in sc and "injected_calls" not in sc and "injection_task" not in sc


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    monkeypatch.setattr(ui, "LOGS", tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd, tmp_path
    httpd.shutdown()


def post(port, path, payload):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def test_logging_and_validation(srv):
    httpd, logs = srv
    port = httpd.server_address[1]
    assert post(port, "/api/log", {"pid": "P001", "type": "decision", "approve": False}) == 200
    assert post(port, "/api/log", {"pid": "../etc", "type": "x"}) == 400
    assert post(port, "/api/nope", {"pid": "P001"}) == 404
    lines = (logs / "P001.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["kind"] == "log"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html") as r:
        assert b"CLEAR" in r.read()
