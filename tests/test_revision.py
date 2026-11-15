"""Checks for the revision tooling: detector task sample and bibliography formatting."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "experiments"))


def test_detector_task_sample_is_deterministic_and_about_a_quarter():
    from detector_baselines import SAMPLE_PERCENT, in_sample
    suites = {"banking": 16, "slack": 21, "travel": 20, "workspace": 40}   # AgentDojo v1 user tasks
    tasks = [(s, f"user_task_{i}") for s, n in suites.items() for i in range(n)]
    picked = [t for t in tasks if in_sample(*t)]
    assert picked == [t for t in tasks if in_sample(*t)]          # deterministic
    assert abs(len(picked) / len(tasks) - SAMPLE_PERCENT / 100) < 0.12
    assert len({s for s, _ in picked}) == 4                        # every domain represented


def test_apa_title_protection():
    from build_bibliography import polish, protect
    t = protect("AgentDojo: a Dynamic Environment for LLM Agents and Large-Scale Studies")
    assert "{AgentDojo}" in t and "{LLM}" in t
    assert "{A} Dynamic" in t                  # first word after a colon is capitalised and kept
    assert "Large-Scale" in t and "{Large" not in t   # ordinary compounds follow sentence case
    e = polish("@misc{k,\n  title = {X},\n  author = {A},\n  year = {2025},\n  howpublished = {arXiv:2501.00001},\n  note = {Preprint}\n}")
    assert "arXiv preprint arXiv:2501.00001" in e and "doi = {10.48550/arXiv.2501.00001}" in e
    e = polish("@inproceedings{k, title={T}, booktitle={22nd USENIX Security Symposium}, month=aug, year={2013}}")
    assert "booktitle={{22nd USENIX Security Symposium}}" in e and "month" not in e
