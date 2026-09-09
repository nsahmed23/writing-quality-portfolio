Two unrelated problems, so two separate answers. Do the flake first: restructuring moves files that your imports and Playwright config point at, and you want a test signal you trust before you start moving things.

## 1. Playwright heading timeout on CI only

I cannot see your `playwright.config.ts`, the spec, the app, or the CI workflow, so the causes below are a ranked hypothesis set with the step that tells them apart, not a diagnosis.

The general shape: "passes locally every time, times out on CI" is almost always a timing or page-state difference, not a bad locator. CI runners are cold and slow (no warm dev server, no browser or module cache, often 2 cores shared by several parallel workers), so a heading that paints in 200 ms locally can take many seconds there, or never render at all because the page went somewhere else.

**1. Capture evidence before changing anything.** Add to `playwright.config.ts`:

```ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

Upload `playwright-report/` and `test-results/` as CI artifacts (`actions/upload-artifact` on GitHub Actions, with `if: always()` so it runs on failure). Then open the failing run locally with `npx playwright show-trace trace.zip`. The DOM snapshot at the moment of timeout answers the question directly, and every later step depends on which answer you get.

**2. Match the snapshot to one of the four common CI-only causes.**

- *The heading is absent and the page is a login screen, error boundary, or empty state.* Auth or seed data differs on CI. The locator was never going to match, so raising the timeout does nothing. Fix the `storageState` / fixture / DB seed.
- *The heading appears late, after an API call.* Genuinely slower on CI. Fix with a deterministic wait, not a bigger global timeout (step 3).
- *Two nodes match the locator.* A skeleton or visually hidden heading coexists with the real one for a moment. Locally the skeleton unmounts before the assertion runs. This surfaces as a timeout whose error text names a strict mode violation and lists both matches, so check the error body, not just the "Timeout 30000ms exceeded" line.
- *The element is present but not stable or visible.* A transition or animation is still running. Headless CI and headed local rendering differ here. Setting `reducedMotion: 'reduce'` in `use` removes this class of difference.

**3. Make the wait deterministic rather than longer.** Wait for the thing the heading depends on:

```ts
const dashboardData = page.waitForResponse(
  r => r.url().includes('/api/dashboard') && r.ok()
);
await page.goto('/dashboard');
await dashboardData;
await expect(
  page.getByRole('heading', { name: 'Dashboard', level: 1 })
).toBeVisible();
```

Avoid `page.waitForTimeout()` and `waitUntil: 'networkidle'`; both are guesses, and `networkidle` never settles if you poll or hold a websocket open. If one assertion genuinely needs longer on CI, raise that one (`toBeVisible({ timeout: 15_000 })`) rather than the global `expect.timeout`, so a real regression still fails fast.

**4. Stop starving the runner.** More workers than cores makes every step slower and converts "slow" into "timeout". On a standard 2-core hosted runner, set `workers: process.env.CI ? 2 : undefined`. Keep `retries: process.env.CI ? 2 : 0` as a shock absorber, but treat a passing retry as an open bug, not a pass; Playwright's HTML report flags those as flaky.

**5. Prove the fix before believing it.** Green once means nothing for a flake. Run the single spec repeatedly on CI in a temporary job: `npx playwright test dashboard.spec.ts --repeat-each=20 --workers=1 --retries=0`. If 20 consecutive runs pass on the runner, you have a fix. Then delete the temporary job.

## 2. Repo structure

Assumption, since I have not seen the tree: this is a TypeScript or JavaScript web app, given the Playwright dashboard test. If it is something else, the layout still holds but the tooling names change.

Go feature-first, not type-first. Grouping by kind (`components/`, `hooks/`, `utils/`, `types/`) looks tidy at 20 files and hurts at 200, because one behavior change then touches five folders and no folder tells you what the app does.

```
src/
  app/                  entry point, router, providers, global styles
  features/
    dashboard/
      components/
      api.ts
      hooks.ts
      types.ts
      index.ts          the only thing outside code may import
    auth/
    settings/
  shared/
    ui/                 generic Button, Dialog; knows no feature
    lib/                fetch client, date and format helpers
    types/
e2e/                    Playwright specs, outside src
```

One rule keeps this from rotting: a feature may import from `shared/`, never from another feature's internals. Cross-feature use goes through that feature's `index.ts`, and anything two features both need moves down into `shared/`. Enforce it mechanically or it will not hold; `eslint-plugin-boundaries` or the built-in `import/no-restricted-paths` rule both do this. Add path aliases (`@/features/*`, `@/shared/*`) in `tsconfig.json` and your bundler config so imports stop being `../../../`.

Migrate in small merged steps, not one big-bang PR:

1. Add the path aliases and create the empty folders. Move nothing. Merge this alone, so a broken alias config is a one-line revert.
2. Move leaf modules first, the ones nothing else depends on downstream (utils, types). Use `git mv` and change no file contents in that commit, so review shows renames and `git blame` still works. If you must edit while moving, use two commits.
3. Move one whole feature, and make `dashboard` the first since you are already in it. Add its `index.ts` and repoint outside imports at it.
4. Turn the boundary lint rule on as a warning, clear the warnings, then flip it to error.
5. Repeat one feature per PR.

Two smaller calls worth making now: colocate unit tests with their source (`Chart.tsx` next to `Chart.test.tsx`) so a move carries the test with it, and do not create a subfolder for a single file. A three-file feature stays flat inside its feature folder.

Also check `testDir`, `webServer.command`, and any relative paths in `playwright.config.ts` after step 3, since moving files is exactly the thing that quietly breaks them.
