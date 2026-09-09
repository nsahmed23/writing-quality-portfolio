I can't see the ledger-svc repo, so two assumptions going in: it's already pushed to a GitHub remote (Actions only runs there, not against the local clone at `C:\Dev\Projects\ledger-svc`), and it's a normal single-module repo with one `go.mod` at the root. The workflow below reads the Go version straight out of `go.mod` instead of hardcoding one, so that part holds regardless of which version you're actually on.

Here's the full setup.

### 1. Create the workflow file

GitHub Actions looks for workflow files in one specific place: `.github/workflows/` at the repo root. Create that folder if it doesn't exist, then add a YAML file inside it, for example `.github/workflows/ci.yml`:

```
ledger-svc/
  .github/
    workflows/
      ci.yml
  go.mod
  go.sum
  ...
```

The filename itself doesn't matter to GitHub; `ci.yml` is just the usual convention.

### 2. Paste this into `ci.yml`

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

      - name: go vet
        run: go vet ./...

      - name: go test
        run: go test ./... -v
```

What each part is doing, top to bottom:

- `on.pull_request.branches: [main]` is the trigger you asked for. This job runs when a PR is opened or updated against `main`, and only against `main`; it ignores plain pushes and PRs targeting other branches.
- `runs-on: ubuntu-latest` picks a Linux runner, the standard default and the fastest, cheapest option. That's fine for typical Go code. If ledger-svc has Windows-only build tags or cgo bindings, which I have no way to see from here, you'd swap this for `windows-latest` instead.
- `actions/checkout@v4` pulls your code onto the runner. Without it there's nothing to run `go vet` or `go test` against.
- `actions/setup-go@v5` installs Go. `go-version-file: go.mod` points it at your `go.mod` so it uses whatever version you've already declared there, instead of a second version number living in the workflow that can drift out of sync.
- `cache: true` is the module caching you asked for. It caches the downloaded module cache keyed on a hash of your `go.sum`, so a PR that doesn't change dependencies restores that cache instead of re-downloading every module from scratch. The first run after adding this workflow is a normal cold run; every run after that reuses the cache until `go.sum` changes. If ledger-svc has no `go.sum`, this step simply has nothing to key off and quietly skips caching; it won't fail the build.
- `go vet ./...` and `go test ./... -v` both use `./...` so they cover every package in the module, not just the root one. `-v` prints each test as it runs; useful while you're first watching this work, easy to drop later if the logs get noisy.

`actions/checkout@v4` and `actions/setup-go@v5` are the current stable major versions as far as I know. If GitHub ever flags either as outdated, bump the number after the `@`; nothing else in the file needs to change.

### 3. Commit and push it

Actions only reacts to what's on GitHub, not your local working copy. From `C:\Dev\Projects\ledger-svc`:

```
git add .github/workflows/ci.yml
git commit -m "ci: add go vet and go test workflow"
git push
```

If `main` is protected against direct pushes, push this to a branch and open a PR like normal instead. Once it's merged into `main`, every PR after that will trigger it. The PR that adds the file itself is a known edge case: it may or may not run on its own first push, so don't read anything into that either way, just confirm it's running cleanly on the next PR.

### 4. Watch it run

Open a PR into `main` and a check named "test" appears at the bottom of the PR, moving from a yellow dot to a green check or a red X. Full logs for each step live under the repo's Actions tab on GitHub if something fails and you need to see why. There's no separate signup or toggle to enable Actions; pushing the YAML file is what turns it on.

### Optional, beyond what you asked

Two small additions worth knowing about once the basics are working:

- Actually blocking bad merges: right now the check runs and reports status, but nothing stops someone from merging a PR with a red X. In GitHub, go to Settings, then Branches, add a protection rule for `main`, turn on "Require status checks to pass before merging," and select the `test` job.
- Cancelling stale runs: if you push several commits to the same PR quickly, each push starts its own run and the earlier ones keep burning CI minutes in the background. This cancels superseded runs; add it near the top of `ci.yml`, alongside `on:` and `jobs:`:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

With steps 1 through 4 done, every PR into `main` runs `go vet` and `go test` automatically, with module downloads cached after the first run.
