Two unrelated problems, so two separate answers. Do the flake first: restructuring the tree while the suite is unreliable means you cannot tell a broken import from a flake.

## 1. The CI-only locator timeout

Start by reading the evidence the failed run already produced, not by re-running. A Playwright trace captures the DOM snapshot, network activity, and console output at the instant the locator timed out, which is the one thing a green local run cannot tell you.

Confirm the config keeps a trace on failure:

```ts
// playwright.config.ts
retries: process.env.CI ? 1 : 0,
use: { trace: 'on-first-retry', screenshot: 'only-on-failure' },
```

and that the workflow uploads artifacts even when the test step fails (without `if: always()` the upload is skipped on red, which is why many repos have no trace to read):

```yaml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: playwright-artifacts
    path: |
      playwright-report/
      test-results/
```

Download that artifact from the last red run and open it with `npx playwright show-trace test-results/**/trace.zip`. Look at the final DOM snapshot and the network panel, then pick the branch it puts you in:

**Heading absent, page sitting on a loader, login screen, or error boundary.** The app never reached the dashboard state on CI. Check the Network tab for a 401/404/500 on the dashboard's data request and the Console tab for a thrown error. The usual causes are a CI secret or env var that is not set on the runner (API base URL, auth key), a database with no seed data so the page renders an empty state with different copy, or a `storageState` auth file that exists on your machine and is never generated in CI.

**Heading present in the snapshot but rendered after the timeout.** This is a speed problem, not a correctness one. CI runners have fewer cores than your laptop and the default `expect` timeout is 5s. Note that "passes locally every time" usually means a warm build, a dev server already running, and no competing workers, so it is not evidence against a timing cause.

**Heading present but the text, role, or match count differs.** A strict-mode violation (two matching nodes) or a formatting difference. CI runs in UTC with a different locale default, so any heading containing a date, currency, or number can fail a string comparison that holds locally.

Fixes, per branch:

1. If it is environment or data, fix the runner, not the test: set the missing variable, seed the fixture in a `globalSetup`, or generate `storageState` in a setup project rather than committing it.
2. If it is timing, use a web-first assertion, which retries until the deadline instead of asserting once: `await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()`. Delete any `page.waitForTimeout` you find near this test; a fixed sleep is exactly the construct that passes on fast hardware and fails on slow. If the dashboard depends on a specific call, wait on the real signal: `await page.waitForResponse(r => r.url().includes('/api/dashboard') && r.ok())`.
3. Raise the timeout only after you know it is speed, and only where it matters: `expect: { timeout: process.env.CI ? 15_000 : 5_000 }`. Raising it blindly hides the environment cases above.
4. If the accessible name is dynamic, anchor on a `data-testid` instead of visible text.

To test the resource-contention hypothesis specifically, set `workers: 1` on CI for one run. If the flake disappears, it is contention or cross-test interference, and the durable fix is test isolation rather than serial execution. To reproduce locally, run `CI=1 npx playwright test e2e/dashboard.spec.ts --repeat-each=20`; if that still passes, run it inside the matching container (`mcr.microsoft.com/playwright:v1.4x-jammy`) so you get the runner's browser build and font set. One more thing to check in the config: if `webServer` starts a dev server on CI but you test a production build locally (or vice versa), you are testing two different apps.

I have not seen your `playwright.config.ts`, the spec, the workflow file, or the trace, so I cannot tell you which branch you are in. The trace's DOM snapshot decides it in about a minute.

## 2. Structuring a flat `src/`

Group by feature, not by file type. Type-first folders (`components/`, `hooks/`, `utils/`) scale badly because a single change touches four directories, and nothing stops any file from importing any other. A shape that works for a TypeScript web app:

```
src/
  app/                 entry point, routing, providers, global styles
  features/
    dashboard/         components, hooks, api calls, types for this feature
    auth/
  shared/
    ui/                genuinely reusable presentational components
    lib/               pure helpers, no app knowledge
    api/               http client, generated API types
e2e/                   Playwright specs
```

The rule that gives this its value: a feature may import from `shared/` and from inside itself, never from another feature's internals. When two features need the same thing, promote it to `shared/` rather than reaching sideways. Keep unit tests colocated as `dashboard/DashboardHeader.test.ts`; only e2e specs live outside `src/`.

Migrate in this order so each step is reviewable and revertible:

1. Add path aliases first (`@/features/*`, `@/shared/*`) in `tsconfig.json` `paths` plus the matching `resolve.alias` in your bundler config. Do this before moving anything, so the moves do not also rewrite hundreds of relative import strings.
2. Move one feature per commit with `git mv` so history follows the file, then run typecheck and the e2e suite before committing. Message form: `refactor(dashboard): move to features/dashboard`.
3. Add the boundary lint rule last, once the tree exists: `eslint-plugin-boundaries`, or `import/no-restricted-paths` if you want to stay within `eslint-plugin-import`. The initial violation count is your remaining backlog, and it stops the flat structure from growing back.

I do not know your framework, repo size, or whether `src/` is a front end, a service, or both, so treat the tree as a template to adapt rather than a target to match exactly. If it is a Go or Rust service the same feature-first principle holds but the conventional folder names differ.

Next action: pull the artifact from your last red CI run and read the DOM snapshot at the point of the timeout. That one observation tells you which of the three flake branches you are in, and everything after it is a small, specific fix.
