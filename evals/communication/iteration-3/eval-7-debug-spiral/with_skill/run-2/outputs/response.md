Pull the trace or screenshot from a failed CI run and look at what's actually on the page when the timeout hits. That's the next step, not another locator or timing change.

All three fixes so far assumed the same thing: that "Metrics" renders late on CI and just needs more time or a better wait. That assumption is now the thing to question. `getByTestId('metrics-heading')` removes any role/name matching issue, and it still timed out the same way. A genuine timing race usually responds at least a little to a longer timeout or a network-idle wait; getting the identical failure across three different strategies points to the heading never rendering on CI, not rendering slowly.

If it never renders, the cause is upstream of the locator. Three likely candidates:

1. The dashboard's data fetch fails only on CI (missing env var, different API base URL, no auth token in CI secrets), so the component branch that renders "Metrics" never runs.
2. CI has no saved login session (Playwright's `storageState`, cached auth cookies that exist locally but not in the CI job), so the page redirects to a login screen instead of the dashboard.
3. Seed data or a feature flag differs on CI, leaving the dashboard in an empty or error state.

To find out which:

1. In `playwright.config.ts`, confirm `use: { screenshot: 'only-on-failure', trace: 'on-first-retry' }` is set; add it if it's missing.
2. Re-run the CI job. About 5 minutes if capture was already on, 10 if you had to add it.
3. Open the trace or screenshot artifact from the failed run.

What does the page show at the timeout: the dashboard with something other than "Metrics," a login page, or something blank or broken? That tells us which of the three it is.
