# Next actions

- **Current state:** RESEARCH_WAVE
- **Highest-value next action:** Complete the minimum evaluator implementation and rerun all RED tests.
- **Why it matters:** Corpus and model outputs cannot be frozen or scored safely without validated storage, matching, blinding, and preservation code.
- **Required context or files:** `tests/`, `src/wqeval/`, `config/`, and the approved plan.
- **Blocked by:** Nothing for objective harness work.
- **Fallback:** If implementation fails, preserve the failing test output and report the exact unsupported contract.
- **Refresh trigger:** Source commits change or the user supplies real human ratings or permissioned author samples.
