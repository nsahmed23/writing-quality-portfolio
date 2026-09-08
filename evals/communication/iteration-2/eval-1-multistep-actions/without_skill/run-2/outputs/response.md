GitHub Actions workflows are just YAML files that live in `.github/workflows/` at the repo root. Once one is pushed to the repo, GitHub picks it up automatically, no separate setup or registration step needed anywhere in the GitHub UI.

Create `.github/workflows/ci.yml` in `C:\Dev\Projects\ledger-svc` with this:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

jobs:
  checks:
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

What each part does:

- `on.pull_request.branches: [main]` is the trigger: this job fires whenever a PR is opened or updated with a new commit against `main`. It won't fire on pushes made straight to other branches.
- `uses: actions/checkout@v4` and `uses: actions/setup-go@v5` pull in prebuilt, reusable steps published by GitHub itself (that's what the "Actions" in GitHub Actions refers to), instead of you writing the git-checkout and Go-install logic by hand. The `@v4` and `@v5` pin the version of each action so a new release upstream doesn't silently change your CI's behavior.
- `go-version-file: go.mod` tells `setup-go` to read the Go version from your `go.mod`'s `go` directive, instead of you hardcoding a version in the workflow that quietly drifts out of sync later.
- `cache: true` is your caching ask. `setup-go` caches the module download cache and the build cache itself, keyed off `go.sum`, so a PR that doesn't touch dependencies reuses the cache instead of redownloading everything on every run. You don't need a separate `actions/cache` step for this; that's the slower, manual route people usually reach for first.
- `runs-on: ubuntu-latest` runs the job on GitHub's hosted Linux runner, regardless of what OS you develop on. That's the normal default and is fine unless you have Windows-only test code.

To wire it up:

1. Create the folder if it doesn't exist yet: `mkdir -p .github/workflows` in Git Bash, or `New-Item -ItemType Directory -Force .github\workflows` in PowerShell.
2. Save the block above as `.github/workflows/ci.yml`. The filename doesn't matter to GitHub, only the location does, but `ci.yml` is a reasonable name.
3. Commit and push it: `git add .github/workflows/ci.yml`, then `git commit -m "ci: add workflow for go vet and go test"`, then `git push`.
4. Open a PR into `main` (or push another commit onto an existing PR branch). GitHub Actions is enabled by default on repos, so there's nothing else to turn on. If an org-level policy has disabled it, Settings > Actions > General will show a banner saying so.
5. Watch it run from either the "Checks" section at the bottom of the PR, or the "Actions" tab on the repo.

One more step worth doing once you've watched it pass at least once: go to Settings > Branches, add a protection rule for `main`, and turn on "Require status checks to pass before merging," then pick the check. It will show up as "CI / checks" (workflow name / job name). That option only appears after the workflow has run at least once; GitHub won't offer a check it has never seen. Without this step, the workflow still runs and reports pass or fail on the PR, but nothing stops a merge if it fails.

I don't have access to the actual repo, so a few things here are assumptions rather than verified facts. I'm assuming `go.mod` sits at the repo root. If your module lives in a subdirectory instead, add `defaults: run: working-directory: <path>` under the job and point `go-version-file` at that same path. I'm also taking "main" as the literal default branch name from your message rather than confirming it. Finally, I can't tell whether `.github/workflows/` already has files in it that this one would sit alongside; a quick look there before you add it is worth doing.
