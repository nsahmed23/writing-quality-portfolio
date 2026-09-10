Two unrelated things, so I'll keep them separate. I can't see your repo, `playwright.config.ts`, CI workflow, or the failed run, so the flake section is ordered by what the symptom pattern implies, not by anything I verified in your code.

## 1. Playwright locator timeout on CI only

Start with the run that already failed. A local rerun can't reproduce the thing that differs, and the trace from the CI failure usually settles this in one look.

```bash
gh run download <run-id> -n playwright-report
npx playwright show-trace test-results/<test-dir>/trace.zip
```

Open the DOM snapshot at the moment of the timeout. It puts you in one of three buckets:

- **Heading absent.** The dashboard rendered an empty, loading, or error state. Cause is data or auth, not timing: missing seed data, an unset env var, an unauthenticated storage state, or an API call that 401s/500s on CI. Check the trace's network tab in the same view.
- **Heading present but not visible.** Layout or viewport. CI headless defaults to 1280x720, which may be narrower than your local window and can collapse the heading behind a mobile nav or an off-screen container. `toBeVisible()` and locator actions wait for visibility, so a present-but-hidden element times out exactly like a missing one.
- **Heading present with different text.** Locale or timezone (CI runners are UTC with a C locale, so a date-formatted or greeting-style heading differs), or the name is interpolated from fetched data that isn't there yet.

If there's no artifact to download, fix that first, since everything else is guessing:

```ts
// playwright.config.ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

```yaml
- uses: actions/upload-artifact@v4
  if: ${{ !cancelled() }}
  with:
    name: playwright-report
    path: |
      playwright-report/
      test-results/
    retention-days: 7
```

One premise worth checking before you spend real time: does it fail on *every* CI run, or only some? If every run, it isn't flake, it's a deterministic environment difference, and retries will only bury it. The HTML report's flaky-vs-failed labels across a few runs tell you which, and the two cases need different fixes.

Once you have a hypothesis, reproduce under CI conditions:

```bash
CI=true npx playwright test --workers=1 --repeat-each=10 -g "dashboard"
```

`CI=true` matters because config defaults branch on it (`reuseExistingServer: !process.env.CI`, retries, worker count), so without it you're running a different configuration than CI does.

Two things to avoid: raising the timeout as the first move (legitimate only after the trace shows the heading did arrive, just late, in which case set `expect: { timeout: 10_000 }` in config rather than sprinkling per-assertion values), and `page.waitForTimeout`, which converts a real race into a slower race. If the heading text comes from fetched data, assert on a stable anchor (`data-testid`, or a role plus a static accessible name) and let `expect(...).toBeVisible()` do the waiting.

## 2. Repo structure

Organize by feature, not by file type. A flat `src/` and a `src/components + src/hooks + src/utils` split fail the same way: to change one behavior you touch four directories, and nothing tells you what may import what.

```
src/
  app/                  entry point, router, providers, global styles
  features/
    dashboard/
      components/
      api/
      hooks/
      index.ts          the feature's only public surface
    <next-feature>/
  shared/
    ui/                 presentational components with no domain knowledge
    lib/                pure helpers
    api/                http client, auth, error mapping
```

Three rules make it hold: dependencies point one way (`app` to `features` to `shared`, never back), a feature imports another feature only through its `index.ts`, and `shared/` never imports from `features/`. Enforce it with `eslint-plugin-boundaries` or `import/no-restricted-paths`, otherwise it re-collapses within a couple of months.

Migration, in slices rather than one big PR:

1. `npx madge --circular src` first. A flat directory hides import cycles well, and moving files is when they start breaking builds.
2. Add the alias so moves don't churn every relative path: `"paths": { "@/*": ["src/*"] }` in `tsconfig.json`, mirrored in your bundler config and your test runner config. Missing the mirror produces module-not-found errors that look like a bad move.
3. Move one feature per commit with `git mv` (preserves blame), run typecheck and tests after each, land each as its own `refactor:` PR.

Sequencing note connecting the two: do the restructure after the e2e suite is trustworthy. A suite that fails on CI for unknown reasons can't tell you whether a move broke something, and that's the only safety net a restructure has.
