Three fixes across three different layers (timeout, wait strategy, selector) and you're getting the exact same failure. That's a strong signal this isn't a Playwright timing or selector problem, it's that the "Metrics" heading (or whatever it depends on) genuinely isn't rendering in CI. We've been guessing without seeing what the CI browser actually shows at the moment it fails, so let's fix that before trying a fourth locator tweak.

**Get a trace or screenshot from the actual failure.** Add this to `playwright.config.ts` if it isn't already there:

```ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
},
```

Push, let CI fail once more, then pull the `playwright-report` / `test-results` artifact and run:

```
npx playwright show-trace trace.zip
```

That shows the DOM, console output, and network requests at the exact moment the locator gave up. If you can't wait on another CI run, drop `console.log(await page.content())` right before the failing assertion and read it out of the CI log instead.

While that's running, the two most likely explanations for "passes locally, always times out in CI" on a heading that depends on loaded data:

- **The dashboard's data fetch is failing or hanging in CI**, often because a `VITE_*` (or similar) env var, API base URL, or secret that's set in your local `.env` isn't set in the CI build. If that request errors or never resolves, the component sits on a loading or error state forever, and no timeout value or selector swap will fix that.
- **CI is hitting an auth wall that local skips.** If your local flow has a seeded session or an already-logged-in browser profile that CI doesn't, the app may be redirecting to a login page instead of the dashboard, so "Metrics" never exists on the page at all.

Once we can see the actual DOM or network state from a failed run, we'll know which of these it is (or something else) and the fix will be obvious instead of another guess.
