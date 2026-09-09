1. Add trace capture and CI retries to `playwright.config.ts`:

```ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',       // records a timeline + DOM snapshots for the retried run
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
});
```

2. Upload the results from your CI workflow so you can open that trace on your own machine:

```yaml
- uses: actions/upload-artifact@v4
  if: ${{ !cancelled() }}
  with:
    name: playwright-results
    path: |
      playwright-report/
      test-results/
    retention-days: 7
```

3. Push, let one run fail, download the artifact, then run `npx playwright show-report ./playwright-report` and open the trace attached to the failing test. Budget one CI run plus about ten minutes of reading; for this symptom that is usually the entire diagnosis.

4. In the trace, select the failing locator step and read the DOM snapshot beside it. One question settles the whole thing: was the heading in the DOM at that moment?

| In the DOM snapshot | Most likely cause | Fix |
|---|---|---|
| Heading absent, page shows a login form or a redirect | CI has no signed-in state. Your local runs reuse a `storageState` file that CI never creates, or the setup project fails quietly and the tests run anyway | Make auth a `dependencies` project in the config, and assert the session cookie exists before writing `storageState` |
| Heading absent, page shows a spinner or skeleton | The data behind the heading is slower or missing in CI: cold database, unseeded fixtures, an API that is mocked locally but live in CI | Wait on the cause, not the clock. `await page.waitForResponse('**/api/dashboard')` before the assertion, or mock the route outright |
| Heading present, text differs | Environment-dependent copy: locale, timezone, a feature flag, or a production build where you run a dev build locally | Assert `getByRole('heading', { level: 1 })` plus a `data-testid`, not the exact prose |
| Heading present and correct, arriving just past 5 seconds | Real slowness. `expect(...).toBeVisible()` waits 5 seconds by default (that is separate from the 30 second per-test timeout), and CI cores are fewer and shared across parallel workers | Raise the timeout on that one assertion, and set `workers: 2` for CI |

I have not seen your repo, your `playwright.config.ts`, your workflow file, or a failing run, so those rows are ranked by how often each turns out to be the answer for this exact pattern, not by evidence from your case.

5. While CI runs, try to reproduce it locally under CI-like conditions. The biggest single difference is usually that CI tests a production build while you test the dev server:

```bash
npm run build
# point webServer.command at your preview server for this run, e.g. `npm run preview`
npx playwright test dashboard --repeat-each=20 --workers=4
```

If all 20 pass, the difference lives in the CI environment (slower shared cores, no seed data, no auth state) rather than in the test file. Stop re-running it locally at that point and wait for the trace.

Two things to skip. Raising the global `timeout` as the opening move turns a 30 second failure into a 60 second failure in three of the four rows above and hides the cause. And "passes locally every time" is not evidence that the test is correct; green locally tells you the two environments differ, not which difference matters.

One config line worth a glance while you wait: if `webServer.reuseExistingServer` is `!process.env.CI`, then CI starts a cold server on every run, so whichever test runs first absorbs the compile or warm-up cost that your always-warm local server never charges you. That produces exactly this symptom, and it moves around as test order changes.

Next: push the config change, let one CI run fail, and open the DOM snapshot at the failing step. Which of the four rows you land in picks the fix.

---

**Separately, the repo layout.** Do that after the flake is closed, not before. A restructure rewrites every import path, and if the flake rate changes afterwards you will have no way to tell whether the move caused it.

The default worth adopting is grouping by feature rather than by file type, in three buckets:

```
src/
  app/                 entry point, routing, providers, global styles
  features/
    dashboard/         components, hooks, API calls, and tests for this feature only
    auth/
  shared/              only what two or more features actually import
```

The rule that keeps it honest: a file starts inside the feature that uses it, and moves to `shared/` on the day a second feature imports it, not in anticipation of one. Migrate one feature per commit, using your editor's move-file refactor so imports update themselves, and add a `@/` path alias before you start so nothing turns into `../../../`.

The exact shape depends on things I cannot see: how many files are actually in `src/`, whether this is one app or an app plus a shared library, and which framework's conventions already apply. Send me the output of `ls src` and I will turn this into a file-by-file move plan, once the flake is closed.
