Create `.github/workflows/ci.yml` in your repo root (`mkdir -p .github/workflows` first, that's the fixed folder GitHub scans for workflow files) and paste this in:

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

      - name: Vet
        run: go vet ./...

      - name: Test
        run: go test ./...
```

1. Commit and push it on a new branch, not directly to `main` (the whole thing below, including watching the first run, takes about 10 minutes):

   ```
   git checkout -b chore/add-ci
   git add .github/workflows/ci.yml
   git commit -m "chore: add CI workflow for vet and test"
   git push -u origin chore/add-ci
   ```

2. Open a PR from `chore/add-ci` into `main` on GitHub. It runs immediately: a `pull_request`-triggered workflow uses the file as it exists on the PR's own branch, so it doesn't need to be merged into `main` first. Actions doesn't need separate enabling on a personal repo (org-owned repos sometimes restrict it).
3. Watch it run under the repo's "Actions" tab, or scroll to the checks section near the bottom of the PR. A green check means `go vet` and `go test` both passed; a red X means one failed; click "Details" to see which step and the output.

If that first run fails with a workflow syntax error instead of a vet or test failure, it's almost always YAML indentation (spaces only, no tabs, two spaces per nested level in the block above) rather than anything about your Go code.

What's in the file: `on.pull_request.branches` is the trigger, it fires on every PR that targets `main`, whether newly opened or updated with a new commit, and stays silent for PRs into any other branch. `runs-on: ubuntu-latest` is the machine GitHub provisions fresh for the run and discards afterward, so nothing installed on it carries over on its own. `actions/checkout@v4` clones your repo onto that machine; without it the later steps have no code to work on. `actions/setup-go@v5` installs Go, and `go-version-file: go.mod` points it at your `go.mod` so it installs whatever version you already build with locally, instead of a version number hardcoded here that quietly drifts out of sync.

Caching: `cache: true` on the `setup-go` step is the whole answer to "not slow." Since the runner is discarded after every run, nothing would otherwise survive between them; this line saves the downloaded Go modules and build cache when a run finishes, keyed on a hash of `go.sum`, and restores them at the start of the next run as long as `go.sum` hasn't changed. The first run downloads everything cold and will be the slowest one; every run after that reuses the cache instead of re-fetching modules.

Two things I could not check, since I have no access to the repo or the internet from here. First: whether `go.mod` sits at the repo root. This assumes one module there, not a nested module or a Go workspace; if it lives elsewhere, both `go-version-file` and the cache key need that path instead. Tell me the layout and I'll adjust it. Second: whether `actions/checkout@v4` and `actions/setup-go@v5` are still the newest major versions. My information is from early 2026 and today is September 2026, so a newer major may exist by now; both pinned versions will keep working regardless. Check their Marketplace pages if you want the latest.

Separately: this workflow running is not the same as it blocking a bad PR. A PR can still merge into `main` with a failing `test` check right now, unless you add a branch protection rule (repo Settings > Branches > add rule for `main` > require the `test` status check to pass). Say if you want that set up too.

Next: paste the YAML above into `.github/workflows/ci.yml`.
