Download the trace from the failed CI run and open it before touching the test: `npx playwright show-trace trace.zip`. A CI-only locator timeout is usually the heading never rendering at all (auth redirect, missing env var, failed data fetch) rather than rendering late, and the trace's failure screenshot separates those two in about a minute. I have not seen your config, your workflow, or the run output, so the order below is the usual cause ranking for this symptom, not a diagnosis of your run.

## Fix the flake

1. Make CI produce a trace, if it does not already. In `playwright.config.ts`: `retries: process.env.CI ? 2 : 0` and `use: { trace: 'on-first-retry' }`. In the workflow, after the test step, add `actions/upload-artifact@v4` with `path: playwright-report/` and `if: always()`; without `if: always()` the upload is skipped exactly when the tests fail. Push and let it fail once, so allow one CI cycle before you have anything to read.

2. Open the trace and read three things in this order: the screenshot at the failing step (is that the dashboard, the login page, or an error state?), the network panel (did the dashboard's data request return 401, return 500, or never fire?), and the DOM snapshot (is a heading present with different text?). This step tells you which one of 3, 4, or 5 applies; you skip the other two.

3. Screenshot shows a login page. CI has no session, and the missing heading is a symptom rather than the problem. Add a setup project that logs in once and saves `storageState`, the cookies and localStorage Playwright replays into every later test:

```ts
projects: [
  { name: 'setup', testMatch: /global\.setup\.ts/ },
  { name: 'chromium', dependencies: ['setup'],
    use: { storageState: 'playwright/.auth/user.json' } },
]
```

   The test user's credentials come from CI secrets, and `playwright/.auth` goes in `.gitignore`.

4. Screenshot shows the dashboard shell with a spinner, a skeleton, or an empty state. The test asserted before the data arrived. Wait on the thing that gates the heading rather than raising the heading's timeout: `await page.waitForResponse(r => r.url().includes('/api/dashboard') && r.ok())` before the assertion, or intercept the endpoint with `page.route` so the test stops depending on backend latency at all. Raising the expect timeout to 30s is worth one run as a diagnostic (green means it is a waiting problem, not a missing element), but keep the higher value only if the app is genuinely that slow for real users.

5. Screenshot shows the heading and the locator still timed out. Then the locator is the problem. `getByRole('heading', { name: 'Dashboard' })` matches the accessible name, so an icon, a count badge, or a visually hidden span inside the `h1` changes what it matches. If a mobile nav renders a second copy, the log says "strict mode violation" instead of timing out, because Playwright treats two matches as an error rather than picking the first, so check which of the two messages you actually got. Reproduce with `CI=1 npx playwright test dashboard --debug`, since `CI=1` turns on the CI branches of your config.

If that did not work, reproduce the load and not just the test. Run against a production build (`npm run build && npm run preview`) rather than the dev server, and repeat the spec: `CI=1 npx playwright test dashboard --repeat-each=20`. A warm local dev server hides two costs that only exist on CI, the first request compiling on demand and a runner with fewer cores serving several parallel workers from one process.

## Repo structure, as a second job

Count the files first: `git ls-files src | wc -l`. Under roughly 30 files, flat `src/` is probably not what is bothering you and moving files will not fix it. Past roughly 80, folders make things findable and the move is worth an afternoon. I cannot see the repo, so I do not know which side of that you are on, and I am assuming a TypeScript frontend app from the dashboard and Playwright; if this is Next.js, Nuxt, or a Go service, follow that framework's prescribed layout instead of the shape below.

Group by feature, not by file type:

```
src/
  app/          entry point, routing, providers
  features/     one folder per user-facing area: dashboard/, auth/, settings/
  components/   UI used by two or more features
  lib/          framework-free helpers: api client, formatting, dates
  test/         fixtures and helpers shared across tests
```

The rule that keeps this stable over time: a file starts inside the feature that uses it, and moves up into `components/` or `lib/` only when a second feature imports it. "It feels shared" is not a second consumer.

Move it in slices:

1. Add a path alias (`@/*` pointing at `src/*`) in `tsconfig.json` and in your bundler config, so imports stop depending on relative depth and each move stops rewriting `../../` chains across the tree.
2. `git mv` one feature's files at a time. `git mv` records a rename, so `git log --follow src/features/dashboard/Chart.tsx` still shows the old history.
3. Run the type-check and the e2e suite after each move, then commit it (`refactor: move dashboard into features/`). Budget about 20 minutes per feature on a small app, most of it import fixes that the type-check finds for you.

Do the flake first: once `CI=1 npx playwright test dashboard --repeat-each=5` passes locally and the CI job is green three runs in a row, the suite is a signal you can trust, and a red run during the restructure means you actually broke something.
