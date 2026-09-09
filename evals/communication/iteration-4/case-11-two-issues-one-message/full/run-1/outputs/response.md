Start with the two-minute check, because most "CI only" Playwright failures reproduce locally once you match what CI does differently:

```bash
npm run build && npm run preview          # serve the built app, not the dev server
CI=1 npx playwright test tests/dashboard.spec.ts --repeat-each=10
```

On PowerShell, set the variable separately: `$env:CI=1; npx playwright test ...`. Two things change versus your normal run. `CI=1` switches on any `process.env.CI` branches in `playwright.config.ts` (the config Playwright scaffolds uses it for `retries`, `workers` and `forbidOnly`), and the built bundle is genuinely different code from the dev server: real minification, no hot-reload shim, production environment variables. If it fails here, you have a local reproduction and the rest is ordinary debugging.

Then settle whether this is flake at all. Open the last ten runs of that job and count the failures. Failing every single time is not flake, it is a deterministic difference between the two environments, and it will be cause 1, 2, 3 or 5 below. Failing roughly one run in three or four is timing, or two tests sharing one database, which is what `--repeat-each=10` above is meant to expose.

Then get the trace from a failing CI run. A trace is a recording Playwright can replay afterwards, including a DOM snapshot of the page at the exact moment the locator gave up, so you read what happened rather than guess at it. Budget about 20 minutes, most of it waiting on the run:

1. In `playwright.config.ts`, under `use`, set `trace: 'retain-on-failure'`, which keeps recordings only for tests that failed and keeps the artifacts small.
2. Add an upload step to the workflow, after the test step:
   ```yaml
   - uses: actions/upload-artifact@v4
     if: always()
     with:
       name: playwright-report
       path: |
         playwright-report/
         test-results/
   ```
   `if: always()` is the part that gets missed. Without it, the step is skipped when the tests fail, which is the only run whose artifacts you actually want.
3. Push, wait for the job to fail, download the artifact.
4. Run `npx playwright show-trace` against the `trace.zip` inside `test-results/` (or drag that file onto https://trace.playwright.dev), click the failed step in the timeline, and look at the DOM snapshot beside it.

What that snapshot usually shows, ranked by how often each turns out to be the cause:

1. **A login page, or a redirect to `/login`.** The saved session is missing. Most setups log in once in a setup project and write `storageState`, a JSON file of cookies and local storage that every other test loads. On CI that file often never gets written, because the setup project did not run or the login credentials come from secrets not exposed to that job.
2. **An empty state.** The heading is data-dependent and CI starts from a fresh database, so the dashboard renders "No data yet" while your local database has rows you created months ago. The test waits for a heading that will never appear. The fix is seeding the fixture inside the test rather than relying on data that happens to be there.
3. **A spinner, plus a pending or failed request in the trace's network panel.** Usually `baseURL` or an API host that only resolves on your machine, or a variable defined in `.env.local`, which is gitignored and therefore absent on CI.
4. **The heading, but with different text.** Interpolated names, counts or dates. CI containers run in UTC and you do not, so `Dashboard, March 3` can read `March 4` there and an exact-text locator misses it. `getByRole('heading', { name: /dashboard/i })` survives that; `getByText('Dashboard, March 3')` does not.
5. **A blank page or an error boundary.** A fault that exists only in the production build, since CI serves the bundle and you develop against the dev server. The console panel in the trace will name it.

I have not seen your `playwright.config.ts`, your workflow file, or the failing run, so that ranking is by frequency across projects, not a diagnosis of yours.

One number in the error message is worth reading first. "Timed out 5000ms" is the `expect` timeout, which defaults to 5 seconds, while actions like `click` get 30. Five seconds is tight for a cold CI runner doing a first page load plus an API round trip. If the trace shows the heading arriving correct but late, raise that one assertion with `{ timeout: 15000 }` instead of the global timeout, so the rest of the suite still fails fast.

Next: open the DOM snapshot at the failed step. Whatever is on that page instead of your heading is the bug, and all five causes above are distinguishable from that one screenshot.

Separately, on the repo layout: group by feature, not by file type. `src/dashboard/`, `src/auth/`, `src/billing/`, each holding its own components, hooks, queries and tests, with `src/shared/` for what two or more features genuinely both use. Type-based folders (`components/`, `hooks/`, `utils/`) look tidy at 30 files and become a search across five directories at 300, because one feature's pieces end up scattered. Do it after CI is green rather than before: a large move rewrites every import path, and while a test is already failing intermittently you lose the ability to tell which change broke what. I have not seen your file list, so that is the default shape rather than a plan for your particular `src/`. Want me to lay out the target tree and the move order once the flake is fixed, as pure `git mv` in one commit and import rewrites in the next, so review and `git bisect` stay readable?
