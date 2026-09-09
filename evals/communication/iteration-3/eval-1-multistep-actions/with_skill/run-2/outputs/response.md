1. Create `.github/workflows/ci.yml` in ledger-svc (`mkdir -p .github/workflows` first if that folder doesn't exist yet; GitHub only reads workflow files from that exact path) with this content:

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

About 10 minutes to get through all four steps here; once it's live, each run takes under a minute unless ledger-svc's test suite is heavy.

2. Commit it on a new branch and push: `git checkout -b chore/add-ci-workflow && git add .github/workflows/ci.yml && git commit -m "chore: add CI workflow (go vet, go test)" && git push -u origin chore/add-ci-workflow`.
3. Open a PR from that branch into main, either `gh pr create --base main --fill` or the GitHub web UI. The workflow runs on this same PR automatically; you don't need to merge to main first. GitHub runs pull-request checks against a temporary merge of your branch and main, so a workflow file that only exists on your branch still fires.
4. Check the PR's Checks tab, or the repo's Actions tab, to watch it run.

What each part of the YAML does, since this is your first workflow (a workflow is the YAML file itself; each time it fires is called a run):

- `on: pull_request: branches: [main]` is the trigger: fires on every pull request whose target branch is main, which is what you asked for.
- `runs-on: ubuntu-latest` picks the runner, the disposable virtual machine GitHub starts to execute your steps and then discards.
- `actions/checkout@v4` and `actions/setup-go@v5` are actions: reusable steps other people wrote and published (checkout pulls your repo's code onto the runner; setup-go installs Go). @v4 and @v5 are the current major versions as of my training; I have no way to check the Marketplace live from here, so if this advice is old by the time you use it, confirm those tags haven't moved.
- `go-version-file: go.mod` reads the Go version from your own go.mod instead of hardcoding one here, so the two can't drift apart. This assumes go.mod sits at the ledger-svc repo root, which I can't verify; if your module lives in a subdirectory, point `go-version-file` at it and add `working-directory: <path>` to the two `run` steps.
- `cache: true` is the module caching you asked for: setup-go saves the downloaded modules and build cache between runs, keyed to a hash of go.sum (it's actually the default in setup-go v4 and later; spelling it out just makes the intent obvious). The first run after adding this still downloads everything cold; every run after that, until go.sum changes, is the fast one.

Two more things I can't check without ledger-svc in front of me: that main is really the default branch (swap the name in `branches: [main]` if not), and that Actions is enabled for the repo (on by default for anything you own; an org policy is the only thing that turns it off, and that shows as a banner on the Actions tab, not a silent failure).

Next: run `mkdir -p .github/workflows`, paste the YAML above into `ci.yml` inside it, and save.
