Here's the minimal setup: one workflow file that triggers on pull requests into main, with module caching built in so repeated runs are fast.

Create `.github/workflows/ci.yml` in the ledger-svc repo with this content:

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
      - name: Check out code
        uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true

      - name: Run go vet
        run: go vet ./...

      - name: Run go test
        run: go test ./...
```

What each part is doing, top to bottom:

- `on: pull_request: branches: [main]` is the trigger. This workflow only runs when a PR is opened or updated against `main`, not on every push to every branch.
- `permissions: contents: read` narrows what this workflow's token can do to read-only. Not strictly required for vet/test, but it's a cheap, sane default rather than leaving the token with its broader defaults.
- `runs-on: ubuntu-latest` is the machine ("runner") the job executes on. GitHub provisions it fresh and throws it away after the run; you don't manage it.
- `actions/checkout@v4` pulls your repo's code onto that runner. Almost every workflow starts with this.
- `actions/setup-go@v5` installs Go. `go-version-file: go.mod` points it at your `go.mod` so it uses whatever Go version you've already declared there, instead of you hardcoding a version that can drift out of sync. `cache: true` is the caching you asked for: it caches downloaded modules and the build cache, keyed on your `go.sum`. The first run populates the cache (slower); every run after that restores it instead of re-downloading, so `go vet` and `go test` start almost immediately.
- The last two steps are the actual checks: `go vet ./...` for static analysis, `go test ./...` for your test suite, both across all packages.

To wire it up:

1. In your local ledger-svc clone, create the folder `.github/workflows` if it doesn't exist yet, and add `ci.yml` inside it with the content above.
2. Commit and push it, on a branch or straight to main, whichever is your normal flow.
3. Open a PR into main. There's no separate "enable Actions" step; GitHub picks up any workflow file that exists on the branch automatically.
4. Check the PR page, or the repo's Actions tab, for a run named "CI." Click into it for step-by-step logs if `go vet` or `go test` fails.

One thing this doesn't do yet: it runs, but nothing stops a PR from merging if it fails. If you want that, go to the repo's Settings > Branches, add a protection rule for `main`, turn on "require status checks to pass," and select the `test` job (it only appears in that list after the workflow has run at least once).

A few things I couldn't check from here, since I don't have access to the repo or your machine: whether `go.mod` sits at the repo root (true for most single-module Go repos; a multi-module layout would need path adjustments), and whether a `.github/workflows` folder or other CI already exists that this would sit alongside. I also can't tell whether the module pulls private dependencies; if `go mod download` fails inside Actions with an auth error, that's almost always a private-module issue (`GOPRIVATE` plus a token or deploy key), separate from the setup above. One more note: `actions/checkout@v4` and `actions/setup-go@v5` are the current major versions as of my knowledge; if GitHub's shipped newer majors since, bump the version numbers, but v4/v5 should keep working regardless.