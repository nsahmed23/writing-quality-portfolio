Open the CI run's trace or screenshot for this test (checking the local run won't show anything, since it passes there) and see what the page actually shows at the moment it times out.

Three fixes so far, three different causes ruled out: slow render (longer timeout), pending requests (`networkidle`), and a fragile accessible-name match (testid). All three failed the same way. That's evidence against those three causes, not evidence that a fourth locator tweak will work. The more likely explanation: the "Metrics" heading never renders on CI at all, because the page is in a different state there, not because the check is wrong.

Three common reasons the state would differ only on CI:

- No authenticated session: if the local run carries a saved login (`storageState` or cached cookies) and CI starts fresh, the dashboard route redirects to a login page that has no "Metrics" heading anywhere on it.
- Missing or different config: an API base URL, feature flag, or secret that's set locally but not in the CI environment, so the dashboard renders an error or empty state instead of the real one.
- No seed data: if the metrics come from a database or fixture that's only populated locally, CI may render a "no data yet" state that skips the heading entirely.

If the CI job doesn't already keep an artifact on failure, add `screenshot: 'only-on-failure'` and `trace: 'retain-on-failure'` under `use` in `playwright.config.ts`, push, and let it fail once more; then open the report CI uploads (often at `playwright-report/index.html`).

Which is it: the normal dashboard minus "Metrics," a login screen, an error message, a stuck loading state, or something else?