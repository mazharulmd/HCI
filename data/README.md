# Scenario fixture format

`scenarios.jsonl` contains one JSON object per constructed case. Each line has an identifier and title; user request; source label, trust class, and excerpt; proposed tool/action/permission; author-assigned attack and expected-decision labels; and a rationale. `attack=true` means the scenario intentionally contains an instruction that conflicts with the user's task or attempts unauthorized behavior. It does not mean every non-attack action is authorized: for example, `email_reply_safe` violates an explicit draft-only request.

The eight examples are synthetic, authored for functionality checks, and not sampled from a population of attacks or people. Use them to exercise code paths only. Do not interpret fixture proportions as rates of attacks in deployed systems. The canonical source is `trust_boundary_lab/scenarios.py`; regenerate JSONL with the snippet in the repository's development instructions after changing fixtures.
