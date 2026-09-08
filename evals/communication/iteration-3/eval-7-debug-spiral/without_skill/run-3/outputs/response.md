Three fixes that each targeted a different cause (slow render, network settling, unstable selector) all failing the same way is itself informative: this is very unlikely to still be a timing problem. If it were, tripling the timeout or waiting on network-idle would have closed the gap at least partially. Neither did, which points toward the heading never rendering in CI at all, not rendering late.

Every attempt so far has been a guess made without seeing what the page actually looks like at the moment of timeout. That's the missing piece before trying anything else.

**Get a trace from the actual CI failure.**

In `playwright.config.ts`:
```ts
use: {
  trace: 'retain-on-failure',
  video: 'retain-on-failure',
  screenshot: 'only-on-failure',
},
```

Make sure CI uploads `playwright-report/` and `test-results/` as artifacts, rerun the job, pull down the failed run's trace, and open it:
```
npx playwright show-trace trace.zip
```

That shows exactly what's on screen at timeout (blank page, stuck spinner, login redirect, error boundary) plus the network requests and console output from that run.

**While you're in there, check the usual reasons something works locally and never renders in CI:**

- Does the API call that populates the metrics widget fire in CI, and does it succeed? A 401, a 404, or a wrong base URL leaves the component stuck in a loading or error state forever, no matter how long you wait or what selector you use.
- Does CI have the same seeded data or authenticated session that your local run has? A missing fixture or test user in the CI database is a common reason a dashboard widget never has anything to render.
- Does the `webServer` block in `playwright.config.ts` mark the app ready as soon as it gets an HTTP response, before the frontend has actually hydrated? On a slower CI runner that gap can outlast any locator timeout you set.
- Any errors in the trace's console panel? A render-time JS error would explain a heading that never appears regardless of wait strategy or selector.

Bring back what the trace shows at the failure point, plus any console or network errors, and we'll know whether this is a data problem, an auth problem, or a CI environment problem, instead of guessing at the Playwright side again.
