GitHub Actions reads YAML files from a `.github/workflows/` folder at the root of your repo and runs them automatically when the events you specify happen (here, a pull request against `main`). No separate service to sign up for; it's built into GitHub and comes with a generous free monthly minutes allowance, more if the repo is public.

**1. Create the workflow file**

In `C:\Dev\Projects\ledger-svc`, create the folder `.github/workflows/` and a file inside it named `ci.yml`. In Git Bash:

```bash
cd C:/Dev/Projects/ledger-svc
mkdir -p .github/workflows
```

Then create `.github/workflows/ci.yml` with this content:

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

      - name: go vet
        run: go vet ./...

      - name: go test
        run: go test ./... -v
```

**2. What each part is doing**

`on.pull_request.branches: [main]` is the trigger: this job runs whenever a PR is opened or updated against `main`, and nowhere else. `actions/setup-go@v5` with `go-version-file: go.mod` reads your Go version directly from `go.mod`, so the workflow always matches whatever version you're actually building with instead of a hardcoded number that drifts out of sync.

`cache: true` is the caching you asked about. `setup-go` caches the module download cache and the build cache for you, keyed off a hash of `go.sum`, so you don't need a separate `actions/cache` step. The first run on your first PR will be a normal cold run since there's nothing to restore yet; every run after that, as long as `go.sum` hasn't changed, restores the cache, which is what makes `go mod download` and the build step fast.

`permissions: contents: read` is a small security default: this job only reads code and runs tests, so it doesn't need write access to the repo, and setting this keeps the automatic `GITHUB_TOKEN` scoped down to that.

**3. Push it and watch it run**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add go vet and go test workflow"
git push
```

Open a PR against `main` (the PR that adds this file will itself trigger it, since the workflow becomes part of the diff). On the PR page, scroll to the checks section at the bottom and click into the "test" run to see live logs, or use the repo's "Actions" tab to see every run across all PRs.

**4. Optional: require it before merging**

As written, the workflow runs and reports pass or fail but doesn't block anything by itself. To stop merges on a red run: open the repo's Settings tab, go to Branches, add a protection rule for `main`, and turn on "Require status checks to pass before merging." The check will be listed as something like `CI / test`, but only after it has run at least once, so do this after your first PR rather than before.

A few things I couldn't check since I don't have the repo: this assumes `go.mod` lives at the repo root and you have a single module. If `ledger-svc` is a monorepo or uses a Go workspace, you'd add `working-directory:` to the `go vet` and `go test` steps, or run them per module. `actions/checkout@v4` and `actions/setup-go@v5` are the current major versions as I know them; worth a quick glance at their Marketplace pages if you want to confirm nothing newer has shipped since.
