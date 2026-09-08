Create `.github/workflows/ci.yml` in the repo (the `.github` and `workflows` folders don't exist yet either, so create those too) with this content:

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

      - name: go vet
        run: go vet ./...

      - name: go test
        run: go test ./...
```

This takes about five minutes to wire up. Once it's in the repo, it runs automatically on every PR after that, no further setup needed.

## What this does

`on: pull_request: branches: [main]` is the trigger: GitHub runs this workflow whenever a PR is opened, or a new commit is pushed to an existing PR, against `main`. `runs-on: ubuntu-latest` is the machine it runs on, a fresh Linux virtual machine (GitHub calls this a "runner") created for the run and thrown away afterward. That machine isn't your Windows machine, and it starts with nothing on it, which is why `C:\Dev\Projects\ledger-svc` doesn't appear anywhere in the file; that path only matters locally, when you're creating this file.

Each entry under `steps:` runs in order on that runner. `actions/checkout@v4` copies your repo's code onto it (skip this step and there's nothing to test). `actions/setup-go@v5` installs Go. I can't see your `go.mod`, so rather than guess a version, `go-version-file: go.mod` tells the action to read it straight from that file, so it always matches your project.

`cache: true` is the caching you asked for. It saves Go's module download cache and build cache between runs, keyed to your `go.sum`, so a run with unchanged dependencies reuses last time's downloads instead of fetching everything again. That's usually the biggest source of slowness in a Go CI job, so this one line covers most of it (it's actually the default already when a `go.sum` file exists, but writing it out makes the intent obvious to anyone reading the file later).

The last two steps are `go vet ./...` and `go test ./...`, run the same way you'd run them locally, across every package in the repo. That assumes a single `go.mod` at the repo root; if ledger-svc has nested modules, those two commands need a `working-directory` pointed at the right folder.

## Get it running

1. Create the file above at `.github/workflows/ci.yml`.
2. Create a branch and commit it: `git checkout -b ci/add-github-actions`, `git add .github/workflows/ci.yml`, `git commit -m "ci: add go vet and go test workflow"`.
3. Push it: `git push -u origin ci/add-github-actions`.
4. Open a PR from that branch into `main`. Opening the PR is what triggers the workflow the first time.
5. Watch it run under the repo's "Actions" tab on GitHub. A green check on the PR means both steps passed; a red X means one failed, and clicking into that step shows the actual `go vet` or `go test` output.

## What I can't check from here

The repo isn't in front of me, so a few things here are assumptions: that `go.mod` sits at the repo root (the point above about nested modules still applies if not); that none of ledger-svc's dependencies live in private repos (if they do, `go mod download` will fail on the runner without extra token setup, since it has no access to your other private repos by default); and that `actions/checkout@v4` and `actions/setup-go@v5` are still the current major versions of those two actions (older majors keep working, but each Marketplace listing will show if a newer one has shipped since).

Separately: this workflow only runs the checks, it doesn't stop a failing PR from merging by itself. For that, go to the repo's Settings, then Branches, add a protection rule for `main`, and require the status check named `CI / test` to pass before merging.

Next: create the file above at `.github/workflows/ci.yml`.