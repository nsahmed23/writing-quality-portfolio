Three unrelated changes (timeout length, network-idle wait, selector strategy) all failing the exact same way is itself the signal: the problem isn't in the test, it's in what CI is serving to the test. If the heading were just slow to appear, 15 seconds plus a network-idle wait would have caught it. If the selector were wrong, the testid swap would have caught it. Neither did, so the Metrics heading most likely never renders on CI at all.

That usually means the app is in a different state on CI, not just slower. Common causes:

- The dashboard's data fetch depends on an API URL, key, or secret that's set locally but missing or different in CI, so the request fails or hangs and the component never mounts.
- Playwright's `webServer` reports ready before the app can actually serve requests, so the test runs against a half-booted server.
- CI builds with different environment variables baked in at build time than your local build.

Rather than guess a fourth fix, let's see what's actually on the page when it fails:

- Fastest: add `await page.screenshot({ path: 'debug.png' })` (or `console.log(await page.content())`) right before the failing assertion, commit, push, and pull the screenshot or log from the CI artifact on the next run.
- More complete: add `trace: 'retain-on-failure'` to the `use` block in `playwright.config.ts`, push, then open the resulting trace with `npx playwright show-trace trace.zip` after the next failure.

Paste back what's actually rendering (blank page, error message, login redirect, stuck spinner, or something else) and we'll fix that instead of the symptom.
