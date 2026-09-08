Here's the minimal setup: one YAML file in `.github/workflows/`, triggered on PRs into main, using `actions/setup-go`'s built-in module cache so you don't have to wire up `actions/cache` by hand.

1. In the repo, create the folder `.github/workflows/` if it doesn't already exist.
2. Inside it, add a file named `ci.yml` (the filename is arbitrary; GitHub picks up any `.yml`/`.yaml` file in that folder).
3. Paste in this workflow:

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

4. Commit that file on a branch, push, and open a PR against main. `pull_request`-triggered workflows only fire from an actual PR, so pushing straight to main won't run this; opening the PR will, and it reruns automatically on every new commit you push to that PR afterward.
5. Watch it run from either the PR page itself (checks appear at the bottom) or the repo's Actions tab.

Quick orientation since you haven't used Actions before: everything in `.github/workflows/` is a workflow GitHub watches for. `on.pull_request.branches: [main]` is the trigger. Each entry under `steps` runs in order on a fresh Ubuntu VM GitHub provides for the job; `actions/checkout` pulls your code onto that VM (skip it and there's nothing to test), and `actions/setup-go` installs Go and, in that same step, sets up caching.

That caching is the part you specifically asked about. `go-version-file: go.mod` points setup-go at your `go.mod` so it installs whatever Go version you've already declared there, rather than me guessing a version number. `cache: true` (already the default in `setup-go@v5`; it's written out here just for clarity) caches the module download cache and build cache, keyed on a hash of your `go.sum`. The first run downloads everything fresh; every run after that restores from cache instead of re-fetching modules, which is what actually keeps it fast. You'll have a `go.sum` automatically as soon as `go.mod` has any `require` line, so this applies without extra setup on your end.

A couple of things I can't confirm without access to the repo: whether `.github/workflows/` already has files in it (if so, just drop `ci.yml` in alongside them rather than replacing anything), and whether `actions/checkout@v4` and `actions/setup-go@v5` are still the newest major versions by the time you set this up. Both have been stable tags for a long time, but I have no way to check the Marketplace from here; if a newer major tag exists, it's fine to use instead.

One first-timer snag: if you push and open the PR but nothing shows up under Actions, check Settings > Actions > General on the repo and confirm Actions is allowed to run there. It's on by default, but some org-level policies turn it off.

Last thing, since you said "runs on every PR to main": this workflow runs and reports pass or fail, but a failing run doesn't block the merge button by itself. To make it required, go to Settings > Branches, add a rule for `main`, turn on "Require status checks to pass before merging," and pick the `test` job (it only shows up in that list after the workflow has run at least once). Skip that part if you just want the results visible for now.
