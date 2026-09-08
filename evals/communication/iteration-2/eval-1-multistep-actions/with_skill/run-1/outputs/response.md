Create `.github/workflows/ci.yml` (`mkdir -p .github/workflows` first, in Git Bash) with this:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - run: go vet ./...
      - run: go test ./...
```

1. Commit that file, push the branch, and open a pull request into `main`. This first PR is what triggers the workflow; nothing needs to land on `main` first.
2. On the PR, open the "CI" check (bottom of the conversation tab, or the repo's "Actions" tab) and confirm `go vet` runs, then `go test`.

What each piece is, since this is your first workflow: the file itself is the workflow, a YAML description of automated steps that GitHub finds because it sits under `.github/workflows/`. `on.pull_request.branches: [main]` is the trigger, firing only when a PR targets `main`. `runs-on: ubuntu-latest` is the runner, the disposable VM GitHub creates per run. `actions/checkout@v4` and `actions/setup-go@v5` are actions, prebuilt steps you reuse instead of scripting yourself; the first pulls your code onto the runner, the second installs Go. `go-version-file: go.mod` points setup-go at your own `go.mod` so it always matches the version you've declared there, rather than a hardcoded number that drifts out of sync later. `cache: true` is the caching you asked for: it saves downloaded modules and Go's build cache between runs, keyed on `go.sum`, so an unchanged dependency set restores in seconds instead of re-downloading. It's already the default in setup-go v5; writing it explicitly just makes clear that's what's giving you the speed. If `ledger-svc` has no external dependencies yet (no `go.sum`), there's simply nothing to key the cache on until you add one, that's not an error.

`go vet` and `go test` are separate steps on purpose: if `vet` fails, the job stops there and `test` is skipped, so the cheap check fails fast instead of waiting on a full test run.

Two assumptions, since I can't see the repo: `go.mod` sits at the repo root (standard for a single-module project; a multi-module layout needs `working-directory:` added to each step), and `main` is genuinely the default branch, which your message already states. I also can't confirm today's actual latest major tags for `actions/checkout` and `actions/setup-go` beyond my training data from early 2026; v4 and v5 are correct as of then and stay safe to pin indefinitely, GitHub patches those same tags rather than retiring them, but check each action's Marketplace page if you want certainty nothing newer shipped since.

If the PR shows no check at all rather than a failing one, check Settings > Actions > General on the repo; some repos have Actions disabled or restricted by default.

Separately: a check that only runs doesn't block a bad merge until you mark it required under Settings > Branches > branch protection rules. Want those steps too?
