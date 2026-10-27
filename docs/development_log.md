# Development log (pre-registration of the frozen configuration)

All design decisions below were made using **only the development split**:
GPT-4o (`gpt-4o-2024-05-13`) traces on the AgentDojo **banking** and **slack**
suites (`important_instructions` attack + benign runs). Everything else
(travel & workspace suites for every model, and all traces of the other
LLMs and of the published defences) is **held out** and was not inspected
before the configuration in `configs/` was committed and frozen. The commit
that introduces this file is the freeze point; `git log` provides the audit
trail.

## Initial design (a priori)
* Tool manifest written from tool signatures/docstrings.
* Risk weights and tier thresholds set from the design rationale
  (`configs/clear_default.yaml`), never fitted.

## Changes made after inspecting the development split
| # | Observation on dev split | Change | Type |
|---|---|---|---|
| 1 | Prompt injections were delivered through Slack *channel names* (`get_channels`), which the manifest had labelled `trusted`. Channel and user names are authored by other workspace members. | `get_channels`, `get_users_in_channel` → `output_trust: untrusted` | correction of a manifest annotation error |
| 2 | Agents rewrite URLs (`www.x.com` → `http://www.x.com`), so lexical attribution failed and values became *unattributed* instead of *user*/*external*. | URL canonicalisation (scheme, `www.` and trailing slash ignored) in provenance matching | attribution robustness |
| 3 | Injections that plant a link/address in an outgoing message to a legitimate recipient ("send www.secure-systems-252.com to Alice") were not escalated: the target was user-endorsed and only *content* carried the attacker's value. | New feature: distinctive tokens (URL, e-mail, IBAN, codes) in content arguments that are attributable only to untrusted content raise taint to `taint_content_external = 0.4` | new risk feature |
| 4 | Fetching a web page changes no persistent state; marking it irreversible promoted every NOTIFY to CONFIRM. Leakage through the URL is captured by the exfiltration feature. | `get_webpage.reversible: true` | manifest annotation |
| 5 | Signature-based ground-truth labels included read-only calls (e.g. reading channels) that are part of the injection task's ground truth but cause no harm. | Signature labels restricted to side-effecting calls | evaluation labelling fix |

No weight or threshold was changed.

## Known limitation noted on dev split
The lexical instruction-likeness signal (and the lexical injection-detector
baseline built from it) matches the *template* of AgentDojo's
`important_instructions` attack almost perfectly. Results that depend on it
are therefore optimistic for template attacks; we report every result also
under an *adaptive, detector-evading attacker* in which all text-based
signals are forced to zero (paper, Sec. 6.4).

## Post-freeze changes (explanation text only)
After the freeze commit, only the **reason strings** shown to users were
extended in `clear/risk.py`: a reason for weak instruction-like phrasing, and
one for irreversible actions promoted from NOTIFY to CONFIRM. Features, risk
scores and tiers are unchanged. We verified this by re-assessing 1,338 tool
calls from 300 randomly sampled GPT-4o episodes with the final code: 0
mismatches in any tier or risk value against the stored evaluation outputs.
The UI also gained a `clear_generic` study condition. This affects no reported
result.

## v2 (combined version), 27 Oct 2026
Ideas from the ChatGPT ("Trust Boundary Lab") and Gemini ("PROV-Guard")
iterations were re-implemented as candidate CLEAR features and evaluated on the
**same development split** (GPT-4o × banking/slack) before any held-out
re-evaluation. The decision rule was fixed before the run: adopt a feature if it
does not raise dialogs per benign task by more than 10% and does not raise
ideal-user ASR.

| Candidate | Origin | Dev result (vs v1) | Decision |
|---|---|---|---|
| Decoding-aware lineage (base64, hex, %-enc., HTML entities, homoglyphs, zero-width, `[at]/[dot]`, rot13) + obfuscation as an injection cue | PROV-Guard DLPA | identical ASR (0%), BU and dialogs (1.108 per benign task) | **adopted** (`configs/clear_v2.yaml`) |
| Lexical goal-drift feature γ (w = 0.3) | PROV-Guard CGASD (goal-mismatch component only) | ASR unchanged (0%), dialogs per benign task +22% (1.108 → 1.351), auto-deny BU −2.7 pp | **rejected**; reported as a negative result |

`configs/clear_default.yaml` (v1) is unchanged, and all v1 results remain reproducible.

v2 domain extension (no effect on AgentDojo): a `code_exec` capability class
(run/execute/shell/command/script/test/...) was added to the envelope lexicon
for the code/IDE tools of the stress benchmarks. No AgentDojo tool carries this
capability, so all AgentDojo results are unaffected.

### v2.1: post-hoc decoder robustness fix (after E1)

**This change was made after seeing held-out E1 results. It is therefore not a
confirmatory result and is reported separately from frozen v2.**

E1 showed that v2 still let 8.1% of attacks through when the whole injection
block was base64-encoded, against 4.1% for the plain block. Two causes were found:

1. Serialised tool output contains literal `\n` escape sequences. The encoded
   payload was glued to them (for example `\nSW1wb3J0...`), so the base64 run
   did not start at a token boundary and was never decoded.
2. Decoded payloads were checked for argument lineage but were not scored for
   instruction-likeness (ι).

`configs/clear_v2_1.yaml` sets `provenance.decode_robust: true`. This
un-escapes literal escapes, scans base64 runs at offsets 0–7 and hex runs at
offsets 0–1, and scores decoded (non-rot13) text for ι. With the flag off, the
code path is byte-identical to v2 (regression test in `tests/test_v2.py`).

Result: E1 block-base64 residual ASR is 4.06%, equal to the plain block on the
same episodes; no episode succeeds laundered that fails plain. On ordinary
held-out traffic, ideal-user ASR and dialogs per benign task are reported in
`results/tables/offline_variants.csv`.
