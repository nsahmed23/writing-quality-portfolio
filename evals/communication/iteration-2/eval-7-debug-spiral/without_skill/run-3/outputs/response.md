Stop tuning the assertion. Three different fixes (timeout, network-idle wait, test-id swap) all failed the same way, which means the problem isn't the locator or the wait strategy, it's that the heading genuinely never renders on CI. That's an environment/content difference, not a timing one, and no fourth selector tweak is going to fix that.

One cheap thing to check first: the error still reads "Timeout 5000ms exceeded" even though turn one bumped the timeout to 15000ms. Either that change never made it into what CI is actually running, or something is overriding it, like an `expect.timeout` or `use.actionTimeout` in `playwright.config.ts`, or a CI-specific project block. Worth confirming the config CI sees matches what you think it does, because if edits aren't landing, more edits won't help either.

Past that, you need to see what's actually on the page at the moment it times out instead of guessing again. If you're not already keeping failure artifacts, add this to `playwright.config.ts`:

```ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
}
```

Push, let it fail once more on CI, then pull the trace from the run's artifacts and open it with `npx playwright show-trace trace.zip`. Check three things:

- What's actually rendered: a login screen, an error banner, a blank shell, or a different heading entirely all point to different root causes.
- The network panel, specifically whatever request loads the metrics data. Is it firing on CI at all, and what status does it come back with?
- The console, for a client-side error that could be aborting the render before the heading ever mounts.

Given it fails every time on CI and passes every time locally, rather than flaking intermittently, the likely causes are things that differ between the two environments, not anything about the test itself: a missing env var or secret on CI (API base URL, auth token) that the dashboard's data fetch needs, an auth/login step (storageState or fixture) that's silently failing on CI and redirecting away from the dashboard before it ever shows metrics, or CI serving a production build against a backend that behaves differently than the dev server you test against locally.

Send over what the trace shows, or just the DOM, network, and console panels at the failure point, and we can pin down which of those it actually is instead of trying a fourth locator strategy.
