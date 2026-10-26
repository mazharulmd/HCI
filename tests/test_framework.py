from fastapi.testclient import TestClient
from dataclasses import replace

from trust_boundary_lab.app import app
from trust_boundary_lab.core import make_decision, risk_assessment
from trust_boundary_lab.scenarios import SCENARIOS, get_scenario

client = TestClient(app)


def test_attack_requires_rejection_in_combined_condition():
    for scenario in SCENARIOS:
        if scenario.attack:
            result = make_decision(scenario, "combined")
            assert result["decision"] == "reject"
            assert result["tool_executed"] is False
            assert result["attack_success"] is False


def test_user_authorized_narrow_action_remains_approvable():
    scenario = get_scenario("delete_requested")
    assert risk_assessment(scenario)["level"] == "moderate"
    assert make_decision(scenario, "combined")["decision"] == "approve"


def test_risk_assessment_does_not_use_evaluation_attack_label():
    scenario = get_scenario("web_page_injection")
    assert risk_assessment(scenario) == risk_assessment(replace(scenario, attack=False))


def test_review_api_returns_explicit_gate_result():
    response = client.post("/api/review", json={"scenario_id": "web_page_injection", "choice": "reject"})
    assert response.status_code == 200
    assert response.json()["attack_success"] is False
    assert response.json()["tool_executed"] is False


def test_unknown_scenario_and_invalid_choice_are_rejected():
    assert client.get("/api/scenarios/missing").status_code == 404
    assert client.post("/api/review", json={"scenario_id": "benign_search", "choice": "maybe"}).status_code == 400


def test_app_serves_review_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "Trust Boundary Lab" in response.text
    assert "Approve simulated call" in response.text


def test_evaluation_counts_and_labels_scripted_evidence():
    from trust_boundary_lab.evaluate import run_evaluation
    rows, summaries = run_evaluation()
    assert len(rows) == len(SCENARIOS) * 4
    assert next(x for x in summaries if x["condition"] == "baseline")["attack_success_rate"] == 1
    assert next(x for x in summaries if x["condition"] == "combined")["attack_success_rate"] == 0
