1. Create `.github/workflows/ci.yml` (make the folder first: `mkdir -p .github/workflows` in Git Bash, or `New-Item -ItemType Directory -Force .github/workflows` in PowerShell) with this content:

```yaml
name: CI

on:
  pull_request:        # run this workflow on every pull request...
    branches: [main]   # ...that targets main

jobs:
  test:
    runs-on: ubuntu-latest        # a fresh Linux VM GitHub provisions for the run
    steps:
      - uses: actions/checkout@v4     # pulls your repo's code onto that VM

      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod     # reads the Go version straight from your own go.mod
          cache: true                  # caches downloaded modules, keyed to go.sum's contents

      - name: go vet
        run: go vet ./...

      - name: go test
        run: go test ./... -v
```

2. Commit and push it:

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add CI workflow for go vet and go test"
git push
```

3. Open a pull request against `main`, or push another commit to an existing PR branch. There's no extra setup step on the GitHub side: it reads any file under `.github/workflows/` as soon as it lands on a branch, and runs it whenever the trigger conditions match.
4. Check the bottom of the PR's page for a check named `test`. The first run is the slow one since nothing is cached yet; later runs reuse the cached modules unless go.sum changes, and finish faster.

Two things above I can't confirm without seeing ledger-svc: whether go.mod sits at the repo root (if it's in a subfolder instead, point `go-version-file` at that path and add a `cache-dependency-path` for its go.sum), and whether a go.sum file exists yet (it will if the module has any dependencies at all; if it doesn't, the cache step can fail outright instead of just skipping caching, so run `go mod tidy` locally once and commit the go.sum it produces). The action versions here, checkout@v4 and setup-go@v5, are the current major versions as of my training; either still works if newer majors exist by now, check the Marketplace listing if you want the latest.

If no check ever shows up on the PR: Actions is on by default for new repos, but confirm at Settings → Actions → General in case it's been turned off.

Separately: once this is passing on a real PR, Settings → Branches → add a rule for `main` → require the `test` status check, so a failing vet or test blocks the merge instead of just showing up as a red X on the PR.

Next: run `go vet ./... && go test ./...` locally before you push, so the first PR run isn't red for something the workflow file had nothing to do with.
