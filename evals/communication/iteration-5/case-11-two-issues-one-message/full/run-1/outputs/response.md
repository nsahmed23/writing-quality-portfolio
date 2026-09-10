Fix the flake first, restructure second. Moving files rewrites every import and moves Playwright's `testDir`, so a red CI run after the move is ambiguous: the move, or the failure you already had?

## The CI-only flake

Read the artifact from the last red run before rerunning anything. A Playwright trace (a recorded timeline with a DOM snapshot at every step) answers the one question that picks the fix: at the moment of the timeout, was the heading absent from the page, present but not visible, or present but rendered later than the wait allowed? Those three states have different causes. About 10 minutes if tracing is already on, plus one CI run if it is not.

1. Download the failed job's artifact, then open it: `npx playwright show-trace test-results/<spec>-<test>/trace.zip`. Scrub to the failing assertion and look at the page as it actually was on the runner. If there is no artifact, tracing is off. Add it and rerun that one job:

```ts
// playwright.config.ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

Upload `playwright-report/` and `test-results/` with `if: always()` on the upload step, otherwise nothing is kept when the tests fail.

2. Read the error string exactly, because two different timeouts look alike. `Timed out 5000ms waiting for expect(locator).toBeVisible()` is the assertion timeout, 5 seconds. `Test timeout of 30000ms exceeded` is the whole-test budget, and the locator is just where it ran out. The first says the render is slightly too slow, the second says something never arrived at all. Both numbers are Playwright's defaults; I have not seen your config, so yours may override them.

3. Establish whether CI fails on every run or only some. "Flake" usually means intermittent, and that split changes which causes below are live, but I cannot see your run history. Look at the last 10 runs of that job, and check `grep -n retries playwright.config.ts`: with `retries: 2`, a test that fails then passes is reported green, so the real failure rate can be much higher than the count of red runs.

### Which cause it is

Ranked by how often each one explains a CI-only heading timeout. I have not seen your app, config, or workflow, so these are the candidates, not a diagnosis.

1. **The dashboard never rendered.** The trace snapshot shows a login page, a bare skeleton, or an error state, and the network panel shows a 401 or a failed fetch. CI has no browser profile carrying yesterday's session and usually no seeded data; your local machine has both. Fix: a `setup` project that logs in once and saves `storageState` (a file holding cookies and localStorage that later tests load), plus seeded fixtures or a stubbed response for the dashboard's data call.
2. **The heading's text is computed, and CI computes it differently.** Runners are UTC and typically en-US, so a heading built from a date, a time-of-day greeting, or a formatted number renders different words than it does at your desk. Signature: the snapshot shows a heading, spelled differently from your locator. Fix: pin `use: { timezoneId: 'America/Chicago', locale: 'en-US' }` in the config, and match on `getByRole('heading')` plus a stable `data-testid` rather than the full string.
3. **It rendered outside the CI viewport, or in the other layout.** Headless CI uses 1280x720 unless you set a viewport; if you run headed locally on a big screen, a responsive layout can swap the `h1` or hide it behind a collapsed nav, and `toBeVisible()` fails on an element that is in the DOM with `display: none`. Signature: the element is in the snapshot but the assertion says not visible, or strict mode reports two matches because the desktop and mobile copies both mounted. Fix: set an explicit viewport, and assert the copy both layouts render.
4. **The runner is simply slower.** Two shared vCPUs, a cold build, no HTTP cache, and a production bundle parsed for the first time can push first paint past 5 seconds where your warm dev server does it in 300ms. Signature: the trace shows the heading appearing after the timeout had already fired. Fix: wait on the real signal instead of a longer blanket timeout, for example `await page.waitForResponse(/\/api\/dashboard/)` before asserting, or `{ timeout: 30_000 }` on that one assertion only.
5. **`webServer` answered before the app was ready.** Playwright polls `webServer.url` and starts the run on the first response, which can come from a server that is not yet serving assets, and `reuseExistingServer: true` can attach a run to a stale server. Fix: point `webServer.url` at a route that returns 200 only once the dashboard is servable, and set `reuseExistingServer: !process.env.CI`.

### Confirm the fix

Run the single spec in a CI job: `npx playwright test e2e/dashboard.spec.ts --repeat-each=10 --retries=0 --workers=<the count CI normally uses>`. Worker count matters because a shared-state race (one test invalidating another's session or seed row) only shows up at the concurrency where it happens. `--retries=0` is what makes a green result mean something.

Do not fix this by raising the global timeout or adding `page.waitForTimeout(3000)`. The first turns a fast failure into a slow one, the second reintroduces the failure the first time the runner is busy.

## Repo structure

Group by feature, not by file type:

```
src/
  app/                entry point, router, global providers
  features/
    dashboard/        components, hooks, api calls, unit tests for the dashboard
    auth/
  shared/             ui/, lib/, hooks/ imported by two or more features
e2e/                  Playwright specs, outside src/
```

The rule that keeps it honest: a file lives in the feature that uses it, and moves to `shared/` the first time a second feature imports it, not before. That is the failure mode of a `components/ hooks/ utils/` split, which is the usual first instinct: those folders collect everything and tell a new reader nothing about what the app does. `features/dashboard` does.

1. Add the path alias before moving anything: `"paths": { "@/*": ["src/*"] }` in `tsconfig.json`, plus the matching resolver in your bundler and test runner (`resolve.alias` for Vite, `moduleNameMapper` for Jest). Imports then stop depending on relative depth, so later moves rewrite far fewer files.
2. Move one feature at a time with `git mv`, run the suite, commit. Keep renames and edits in separate commits so `git blame` and review stay readable. On Windows and macOS a case-only rename (`Dashboard.tsx` to `dashboard.tsx`) needs two `git mv` steps through a temporary name, because the filesystem is case-insensitive and Git is not.
3. Keep `e2e/` at the repo root rather than under `src/`, so Playwright's `testDir` never moves when app code does.

Sizing: under 50 files in `src/`, about an hour. Two or three hundred, most of a day, nearly all of it fixing imports, and less than that with the alias in place first. I cannot see your repo, so `dashboard` and `auth` are guesses from the test you mentioned; the real `features/` names come out of your routes.

Done means: the dashboard spec passes 10 consecutive CI runs with `retries: 0` (one green run proves nothing against an intermittent failure), and after each move commit `npx tsc --noEmit` and that same spec are still clean.
