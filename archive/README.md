# Earlier iterations (archived, unchanged)

This project was attempted with three AI research assistants. The combined
version at the repository root builds on all three. The two earlier iterations
are kept here **exactly as they were produced**, including their own commit
histories (see `git log -- archive/`), so that every claim in
`docs/prior_iterations_audit.md` can be checked.

| Folder | Produced with | Former branch | Last commit |
|---|---|---|---|
| `chatgpt-trust-boundary-lab/` | ChatGPT | `research/source-to-action-review` | `31bdb7a` |
| `gemini-prov-guard/` | Gemini | `research/prov-guard-hci-defense` | `5bfbe43` |

**Do not cite results from these folders.** The audit documents their
limitations. In particular, the PROV-Guard "user study" results are produced
by a simulator with hard-coded effect sizes, and its benchmark is separable by
a single provenance rule. The parts reused by the combined version are vendored,
blinded to labels, in `third_party/`.

These folders are not part of the test suite or the reproduction scripts.
