Before trying a fourth fix, check whether CI actually ran the last one. You said the testid swap still fails with "same timeout." If the timeout value in that CI error is still 5000ms, even though the locator timeout was raised to 15000ms in the first fix, none of the last three changes have reached CI at all, and the debugging has been aimed at the wrong layer.

Open the log from the most recent failing run. Does it report 5000ms or 15000ms? That one number tells you which of two different problems you're actually facing, and takes under a minute to check.

**If it still shows 5000ms:** CI isn't running what you think it's running. Check: the job is building the branch or commit that actually has your changes, not a stale checkout; there's no separate CI-only Playwright config (an env-based override, a dedicated `playwright.config.ci.ts`) setting its own timeout; and no build cache (a Docker layer, `node_modules`, a prebuilt output) is serving an old version of the app or test.

**If it shows 15000ms:** the changes are reaching CI, so this is a genuine CI-only difference, not a timing problem. All three fixes so far assumed the heading renders late, just slowly or awkwardly selected. A longer wait, a network-idle wait, and a stable testid all failing the same way is evidence against that assumption: the heading most likely never renders on CI at all. The dashboard is probably sitting in a different state: a login redirect because CI starts with no saved session, a failed metrics fetch because an env var or API URL that's set locally isn't set in CI, or a backend dependency that isn't ready when the test runs.

Confirm which, instead of guessing again:

1. Add `screenshot: 'only-on-failure'` and `trace: 'retain-on-failure'` to the `use` block in `playwright.config.ts` (skip this if you already capture them).
2. Rerun CI once.
3. Open the result: `npx playwright show-trace <path-to-trace.zip>`, or the screenshot directly.

The page itself will show which one: a login screen, an error, a blank page, or the real dashboard with different content.
