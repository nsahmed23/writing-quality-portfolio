1. Create `.github/workflows/ci.yml` in the repo (`mkdir -p .github/workflows` first if that folder doesn't exist yet; that's simply where GitHub Actions looks for workflow files) and paste in the YAML (a plain-text, indentation-based config format) below. About 10 minutes end to end, most of it spent waiting on the first run to finish.
2. Commit it on a new branch and push: `git checkout -b chore/add-ci-workflow && git add .github/workflows/ci.yml && git commit -m "chore: add go vet and go test workflow with module caching" && git push -u origin chore/add-ci-workflow`.
3. Open a PR from that branch into `main` (GitHub prompts you for this right after the push, or run `gh pr create --base main` if you have the GitHub CLI installed).
4. Open the PR on GitHub and click the "Checks" tab (where GitHub lists automated results for the PR). `go vet` and `go test` run there automatically, nothing else to register or turn on.

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
        run: go test ./...
```

**What each part does, top to bottom:**

- `on: pull_request: branches: [main]` is the trigger: it fires whenever a PR's base branch (the one it's merging into) is `main`, whatever the source branch is called. That's what makes this run on every PR to main. `permissions: contents: read` sits next to it and caps what the workflow's token can do; since this job only reads code, it gets nothing more.
- `test:` under `jobs:` is just this job's name, a job being the group of steps that run together; call it anything you like. `runs-on: ubuntu-latest` sets the runner: the disposable Linux machine GitHub provisions to execute it. Free for public repos; private repos get a monthly free-minutes allowance, then billed per minute past that.
- Each entry under `steps:` runs in order. `actions/checkout@v4` is the first one: an action (a packaged, reusable chunk of automation someone else published, referenced by name and version) that pulls your repo's code onto the runner.
- `actions/setup-go@v5` installs Go. `go-version-file: go.mod` points it at your `go.mod` so it reads the Go version from there instead of you hardcoding one that can drift out of sync with the module.
- `cache: true` is the caching you asked for, built into `setup-go` itself rather than a separate action you wire up by hand. It caches both the downloaded module files and the compiled build output, keyed to the contents of your `go.sum`: unchanged dependencies mean a fast restore, a changed `go.sum` invalidates it and a fresh cache gets saved after the run.

The last two steps are plain shell commands, `go vet ./...` and `go test ./...`, run across every package in the module (that's what `./...` means).

**A few things I can't verify from here:**

- This assumes `ledger-svc` is already pushed to GitHub. Actions is a GitHub-hosted feature; it does nothing for a repo that only exists locally or is hosted somewhere else like GitLab.
- `go-version-file: go.mod` assumes one `go.mod` at the repo root. If the repo has more than one module, or a `go.work` file, the vet and test steps need to target each module, or run with a `working-directory` pointed at the right one.
- If any dependency lives in a private repo, `go mod download` fails here with an auth error. Fixing that means setting `GOPRIVATE` and handing the job a token, which is separate setup from this.
- The action versions above (`checkout@v4`, `setup-go@v5`) are current as of what I know; I don't have live access to check the Marketplace right now. A deprecation warning on a run is GitHub telling you to bump the version number next to the action it's attached to.

Merging into `main` still works even if `go vet` or `go test` fails. This workflow only reports the result; it doesn't block anything by itself. To make a failing check stop a merge, add it as a required check under Settings, Branches, then the branch protection rule for `main`. GitHub only offers it in that list after the workflow has run at least once.

Next: create the file, paste in the YAML above, and push it on a new branch. GitHub Actions runs the checks automatically the moment that branch has an open PR against `main`.
