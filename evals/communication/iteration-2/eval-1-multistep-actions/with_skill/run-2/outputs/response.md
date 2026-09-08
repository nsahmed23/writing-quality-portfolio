1. From the repo root (`C:\Dev\Projects\ledger-svc`), create `.github/workflows/ci.yml` (`mkdir -p .github/workflows` first) with this:

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

2. Commit and push that file, then open a pull request against `main`; the PR that adds this file is also the first one it runs on, since GitHub reads workflow files from the pull request's branch.
3. On GitHub.com, open the repo, click the Actions tab, and confirm the run shows two green checks: `go vet` and `go test`.

No signup or settings change needed first: Actions is on by default for a repo you own, so this file is the entire setup. A quick vocabulary note since Actions has its own terms: everything under `.github/workflows/` is a workflow (an automation definition), and GitHub runs any workflow whose trigger matches an event. `on.pull_request.branches: [main]` is that trigger: any PR opened or updated against `main` starts a run. Each run happens on a fresh, temporary machine called a runner, not on your computer, so the first step in nearly every workflow is `actions/checkout@v4`, which clones your repo onto the runner (it starts out empty).

`actions/setup-go@v5` installs Go on the runner. `go-version-file: go.mod` points it at the version already declared in your `go.mod`, so the workflow can't drift out of sync with what you build locally. `cache: true` is the caching you asked for: it saves the downloaded module cache and build cache between runs, keyed to your `go.sum`, so a run where dependencies haven't changed skips re-downloading them instead of pulling every module fresh.

`go vet` and `go test` run as two separate steps rather than one chained with `&&`, so if one fails, the Actions tab shows which one, not just that a step failed.

I don't have access to ledger-svc, so three things I couldn't check: that `go.mod` sits at the repo root (if it's in a subdirectory, `go-version-file` and the two `run` steps need a matching path); that `go vet ./...` and `go test ./...` cover your whole module rather than one of several in a monorepo; and whether any dependency lives in a private repo, which would make plain `go test` fail on the runner with a permission error, needing `GOPRIVATE` (the env var listing which module paths are private) plus a token added first. Separately, `@v4` and `@v5` on the two actions are current as of what I know; if GitHub flags a newer major version in its UI by the time you add this, bumping the tag is safe.
