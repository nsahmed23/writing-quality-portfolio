Two questions, so two answers. Do the flake first and leave the restructure until CI is green; reasoning for that order at the bottom.

I can't see your repo, your `playwright.config.ts`, or the CI logs, so everything below is ranked by likelihood rather than confirmed against your setup.

## 1. Playwright: locator timeout on the dashboard heading, CI only

### First, split the problem

"Flake" and "CI only" pull in different directions, and which one is actually true changes the entire diagnosis. Look at the last ten CI runs of that test:

- **Red on every run** means it isn't flake at all, it's a deterministic environment difference. Something about CI makes the app render a different page than it does locally. This is the easy case.
- **Red on some runs** means real timing or test-isolation trouble, usually parallel workers contending over shared state, or a cold start that sometimes loses the race.

That one check narrows the search a lot, so do it before touching any config.

### Second, get a trace instead of guessing

A locator timeout means the element never appeared. The only question that matters is what was on the page instead, and the trace viewer answers that in about thirty seconds.

```ts
// playwright.config.ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

Assuming GitHub Actions, upload the results even when the job fails:

```yaml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: playwright-report
    path: |
      playwright-report/
      test-results/
    retention-days: 7
```

Then download and run `npx playwright show-trace test-results/<test-dir>/trace.zip`. The DOM snapshot at the failing step shows you the actual rendered page, and that tells you immediately which of the following you're looking at.

### Likely causes, roughly in order

1. **A missing or wrong env var**, so the app renders a login redirect, an error boundary, or an empty state where the dashboard should be. Client-side variables (`VITE_*`, `NEXT_PUBLIC_*`) are baked in at build time, so one that's present in the test job but missing from the build job produces a broken bundle with no error anywhere in the log.
2. **No auth state on CI.** Locally you have a logged-in session sitting in your browser profile or in a gitignored `storageState.json`, and CI has neither, so the test lands on the sign-in page. Confirm the auth setup project actually runs in the CI job and writes its state file.
3. **The server isn't really up.** Use `webServer` with a `url` health check rather than a port guess or a sleep, and `reuseExistingServer: !process.env.CI`. Also check whether CI runs a production build while you run the dev server locally, since those can differ in routing and asset loading.
4. **Data timing.** If the heading text comes from a fetch, you're racing the API. Deterministic mocking with `page.route()` is the durable fix; waiting on the specific response is the smaller one.
5. **The runner is just slow.** Hosted runners are typically 2 to 4 shared vCPUs and can be several times slower than your laptop on cold JS work, and that is enough to blow a default assertion timeout. This is the *least* interesting cause, so only accept it after the trace has ruled out the others.
6. **Test isolation under parallelism.** If tests share a seeded user or database row, running at full worker count on CI surfaces collisions that a serial local run never hits. Quick experiment: set `workers: 1` on CI for one run. If the failure disappears, it's shared state, not slowness, and raising timeouts will never fix it.
7. **Timezone.** CI runs in UTC. If the heading includes a date or a greeting, the rendered text differs from yours near midnight. Cheap to rule out, occasionally the whole answer.

### One timeout detail people get wrong

Playwright's assertion timeout defaults to 5s and is separate from the 30s test timeout. Raising `timeout` in your config does nothing for `expect(locator).toBeVisible()`. If you do decide the runner is genuinely slow, the knobs are `expect: { timeout: 15000 }` globally, or a per-assertion `{ timeout: 15000 }`. Never reach for `page.waitForTimeout()`; it converts a fast failure into a slow one and hides the cause.

To reproduce locally, run `CI=true npx playwright test --repeat-each=20` against a production build. `CI=true` changes retries, worker count, and `reuseExistingServer`, so it exercises the config path CI actually takes.

## 2. Structuring the repo

### Organize by feature, not by type

The instinct when `src/` is flat is to add `components/`, `hooks/`, `utils/`, and `types/`. Resist it. That splits every single feature across four directories, so a one-feature change becomes a four-directory diff, and `utils/` grows into the same undifferentiated pile you started with. Group by what the code is *about*:

```
src/
  app/                 # entry, routing, providers, global styles
  features/
    dashboard/
      DashboardPage.tsx
      useDashboardData.ts
      dashboard.api.ts
      dashboard.test.ts
      index.ts         # the feature's public surface
    auth/
    settings/
  shared/              # only things 2+ features actually import
    ui/
    lib/
    api/
```

The rule that keeps `shared/` honest: code moves there when a *second* feature imports it, not in anticipation of that. Until then it lives next to its only consumer. This is what prevents the new structure from decaying back into a junk drawer.

### Make the move cheap and reviewable

Do it as a single moves-only PR: `git mv` and import-path updates, zero behavior edits. Git tracks renames, so the diff reads as renames rather than thousands of added and deleted lines, and reviewers can actually approve it. If other branches are open, merge or land them first, because a rename PR conflicts with everything.

Set up path aliases in the same PR so imports stop being relative spaghetti and future moves don't churn every file:

```json
// tsconfig.json
{ "compilerOptions": { "baseUrl": "src", "paths": { "@/*": ["*"] } } }
```

Mirror it in `resolve.alias` in your bundler config, or the build and the type-checker will disagree.

### Then enforce it

Structure without enforcement reverts within a month. `dependency-cruiser` is the better tool here (`eslint-plugin-import`'s `no-restricted-paths` also works). Three rules cover it: features may import from `shared`, `shared` may never import from `features`, and features may not import each other directly. Run it in CI alongside the tests.

## Why this order

Fix the flake first. A restructure moves every file at exactly the moment you need your mental map of the codebase intact, and if the flake is still live afterwards you won't know whether it's the original bug or something the move broke. A red CI plus a 200-file rename is the worst debugging position to be in.

Land the flake fix, confirm ten consecutive green runs, then do the restructure as a moves-only PR against a green baseline.
