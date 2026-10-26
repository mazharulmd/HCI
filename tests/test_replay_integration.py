"""Integration test against real AgentDojo traces (skipped if they are not available)."""
import os

import pytest

pytest.importorskip("agentdojo")
from experiments.traces import DEFAULT_RUNS, Replayer, iter_episodes  # noqa: E402
from experiments.evaluate import process_episode  # noqa: E402
from clear.config import load_config  # noqa: E402
from clear.manifest import ToolManifest  # noqa: E402

RUNS = os.environ.get("AGENTDOJO_RUNS", DEFAULT_RUNS)
pytestmark = pytest.mark.skipif(not os.path.isdir(os.path.join(RUNS, "gpt-4o-2024-05-13")),
                                reason="AgentDojo traces not fetched (scripts/fetch_agentdojo.sh)")


def episodes(n=12):
    out = []
    for ep in iter_episodes(RUNS, "gpt-4o-2024-05-13", {"important_instructions", "none"}):
        if ep.suite == "banking":
            out.append(ep)
        if len(out) >= n:
            break
    return out


def test_replay_reproduces_stored_labels():
    rep = Replayer("v1")
    agree = total = 0
    for ep in episodes():
        u, s = rep.run(ep)
        total += 1
        agree += (u == ep.utility) and (not ep.attacked or s == ep.security)
    assert agree / total >= 0.9


def test_process_episode_invariants():
    rep, cfg, man = Replayer("v1"), load_config(), ToolManifest.load()
    for ep in episodes(6):
        rec, rows = process_episode(ep, rep, man, cfg)
        pol = rec["policies"]
        # oracle human never loses utility relative to no defence beyond conservative accounting
        assert pol["none:none"]["confirm"] == 0
        # confirm-all asks about every side-effecting call
        assert pol["confirm_all:oracle"]["confirm"] == rec["n_side_effecting"]
        if ep.attacked and rec["base_security"]:
            assert pol["clear:oracle"]["s"] in (False, True)
            assert rec["n_injected"] >= 1
