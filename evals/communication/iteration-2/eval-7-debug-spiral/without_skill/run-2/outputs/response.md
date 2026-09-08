Three different fixes, three identical failures. That's actually useful signal: it rules out timing and locator strategy as the cause. Raising the timeout, waiting for network idle, and switching to a stable `data-testid` locator all failed the same way, so the heading isn't slow to show up, it isn't showing up at all in CI. Something about what's rendering (or failing to render) on CI differs from local, and no amount of waiting or re-selecting fixes that.

Time to stop changing the test and look at what CI actually rendered when it failed.

1. **Turn on evidence capture for the next CI run.** In `playwright.config.ts`:

```ts
use: {
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

Make sure your CI workflow uploads `playwright-report/` (or `test-results/`) as a build artifact so you can pull it down. Open the trace with `npx playwright show-trace trace.zip`, or open the HTML report. That gives you the real DOM, console output, and network activity at the exact moment the locator gave up, instead of another guess.

2. **When you have that, check these, in order of likelihood for an authenticated dashboard route:**
   - Auth/session state. Confirm CI actually lands on the dashboard and not a login page. Local runs often carry a cached session or seeded storage state that a clean CI run doesn't have.
   - The API call behind the metrics data. Check the network panel in the trace for the request that populates that section. A 401, 404, or 500 there, often from a missing env var or secret that only exists in your local `.env`, would leave the component in an error or empty state instead of rendering the Metrics heading, regardless of timeout or selector.
   - Build/server mismatch. If Playwright's `webServer` boots the app for CI, confirm it's serving the same thing local does (dev server versus a production build can render different markup) and that the readiness check actually reflects the dashboard being usable, not just the process being alive.

3. **If the trace still doesn't make it obvious**, add a temporary line right before the failing assertion so the next run hands you something concrete instead of just a timeout:

```ts
await page.screenshot({ path: 'debug.png', fullPage: true });
console.log(await page.content());
```

Grab the trace, screenshot, or page content from an actual CI failure and share what it shows. That tells us what's actually different about CI, and we fix that instead of trying another locator.