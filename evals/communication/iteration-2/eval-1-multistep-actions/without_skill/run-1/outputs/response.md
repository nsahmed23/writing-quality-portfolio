A GitHub Actions workflow is just a YAML file under `.github/workflows/` in your repo. GitHub watches that folder and runs whatever's in it based on the triggers you define; there's no dashboard setup or separate registration step, and Actions is on by default for repos on github.com unless an org admin disabled it under Settings > Actions > General.

Create `.github/workflows/ci.yml` in `C:\Dev\Projects\ledger-svc`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true

      - name: go vet
        run: go vet ./...

      - name: go test
        run: go test ./... -v
```

**What each piece does:**

- `on.pull_request.branches: [main]` fires the workflow whenever a PR is opened, or a new commit is pushed to an open PR, targeting `main`. That alone covers "every PR to main."
- `actions/checkout@v4` pulls your code onto the runner (a fresh Ubuntu VM GitHub provisions per job). Almost every workflow needs this as its first step.
- `actions/setup-go@v5` installs Go. `go-version-file: go.mod` reads the version from your `go.mod`'s `go` directive instead of hardcoding it a second time in the workflow.
- `cache: true` is the caching you asked for: it caches the module download cache and build cache, keyed on a hash of `go.sum`. The first run is slow because it downloads everything; every run after that reuses the cache and only re-downloads when `go.sum` changes. No separate `actions/cache` step needed.
- `permissions: contents: read` isn't required for this to function; it just keeps the auto-generated `GITHUB_TOKEN` read-only, which is all this workflow needs.
- The two `run` steps are the actual checks. If `go vet` fails, the job stops there and `go test` never runs, so you get the cheap failure fast.

**To ship it:**

1. `mkdir -p .github/workflows` (Git Bash), and save the YAML above as `ci.yml` inside it.
2. Commit and push: `git add .github/workflows/ci.yml && git commit -m "ci: add go vet and go test workflow" && git push`
3. Open (or update) a PR against `main`. GitHub picks the workflow up automatically, no dashboard setup required. The run appears under the PR's checks and under the repo's "Actions" tab.

Two things that catch first-timers. The workflow passing or failing doesn't block the merge button by itself; it only reports a status. To make a red check actually stop a merge, go to Settings > Branches, add a protection rule for `main`, and mark the `test` job as a required status check (it has to run at least once on some PR before GitHub offers it in that list). Separately, if any of `ledger-svc`'s tests hit a real database or another live dependency instead of a mock, plain `go test ./...` will fail on the runner since nothing's listening on the other end; that needs a service container added to the job, or those tests skipped in CI. I can't see your test suite, so I don't know if that applies here.

A few things I couldn't check without the repo: whether `go.mod` sits at the root (if `ledger-svc` is a multi-module workspace, `go vet ./...` and `go test ./...` only operate on the module rooted where you run them from, so you'd need per-module steps instead), and what Go version `go.mod` declares. Also worth flagging: `checkout@v4` and `setup-go@v5` are the versions I'm confident are correct as of my training data; I have no live access to the Marketplace right now, and both get new majors periodically, so a quick glance at each action's repo page before you commit to it long-term is worth doing.

If you want more later: add `push: branches: [main]` alongside `pull_request` to also verify after merges land, look at `golangci-lint`'s own action if you want linting beyond `vet`, and pin the two actions to a commit SHA instead of a version tag if you want to harden against a tag being repointed.
