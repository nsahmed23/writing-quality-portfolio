Three fixes targeted the wait and the selector: a longer timeout, a `networkidle` wait, and a stable `data-testid`. All three time out the same way. That's strong evidence against slow rendering, pending requests, and a bad selector as the cause; the heading isn't late or mislabeled, it's not on the page at all when the test gives up.

Every fix so far assumed the dashboard eventually renders correctly on CI and the test just wasn't catching it right. That assumption hasn't been checked, and it's the one to check now, not the wait or the locator.

The question that settles it: what's actually on the page at the moment of timeout on CI? A login screen points to auth or session state not being set up the same way there. An empty or error state points to the metrics API call failing or being misconfigured on CI. The dashboard with different content than local points somewhere else entirely, worth chasing only once those two are ruled out.

Check `playwright.config.ts` for `trace: 'on-first-retry'` or `screenshot: 'only-on-failure'`. If either is already set, pull the artifact from the last failed CI run, a two-minute look. If neither is set, add `trace: 'on-first-retry'`, push, and pull the trace from the next CI failure instead.

Next: open that trace or screenshot and tell me which of the three you're looking at.
