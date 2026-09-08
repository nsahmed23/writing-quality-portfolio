GitHub Actions workflows are YAML files under `.github/workflows/` in the repo. Each one declares when it runs (`on:`), plus one or more jobs made of steps that execute on a fresh virtual machine. For what you want, one workflow with one job covers it: trigger on PRs into main, check out the code, install Go with module caching, then run `go vet` and `go test`.

In `C:\Dev\Projects\ledger-svc`, create `.github/workflows/ci.yml` (making the folders too, since they likely don't exist yet) with this content:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

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
        run: go test ./... -v
```

Commit that file and push it on a branch, then open a PR into main. You don't need to merge it first to see it work: GitHub runs `pull_request`-triggered workflows using the workflow file as it exists in the PR itself, so the same PR that adds `ci.yml` will trigger it. On the PR page, scroll to the checks section near the bottom; you'll see a check called `CI / test` start running, then turn into a green check or a red X, with a "Details" link to the `go vet` and `go test` output.

On what each part does: `branches: [main]` limits the trigger to PRs targeting main. `actions/checkout@v4` pulls your code onto the runner, since the VM starts empty. `actions/setup-go@v5` installs Go; `go-version-file: go.mod` reads the version straight from your own go.mod, so CI always matches what you build with locally. `cache: true` caches downloaded modules and Go's build cache between runs, keyed on your go.sum (this is actually the default already, but writing it explicitly makes clear that's what's happening). The first run is slow because it downloads everything; every run after that restores the cache instead, as long as go.sum hasn't changed, which is what keeps it fast.

Once this is working, two follow-ups worth doing. First, add a branch protection rule so main can't be merged into with a failing check: Settings > Branches > add rule for main > "Require status checks to pass before merging" > select `CI / test`. Second, if the Actions tab shows workflows as disabled when you get there (uncommon on a personal repo), turn them on under Settings > Actions > General.

A few things I can't verify without the repo. Your Go version doesn't matter here since the workflow reads it straight from go.mod. I don't know whether ledger-svc is a single module at the repo root or has nested modules or a go.work workspace; the commands above assume one go.mod at the root, so a multi-module layout would need vet and test run per module instead. I also don't know if it depends on any private Go modules, which would need extra authentication added to the workflow that isn't included here. And I can't check live whether `actions/checkout@v4` and `actions/setup-go@v5` are still the newest major versions; if GitHub or Dependabot flags a newer one when you add this, taking the update is safe.
