Two separate answers below. Do the CI failure first: restructuring will move files the tests reach through, and you want a suite you trust before you start moving things.

## 1. Playwright timeout on CI only

Start by disbelieving the word "flake." "Passes locally, fails on CI" usually means the two environments genuinely differ and CI is the one telling the truth. A real flake fails maybe 1 run in 20 on the same machine. If it fails on CI consistently or near-consistently, that is a difference, not randomness, and the difference is the bug.

Get evidence before changing anything. In `playwright.config.ts`:

```ts
export default defineConfig({
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
```

Then upload `playwright-report/` and `test-results/` as a CI artifact, with `if: always()` on the upload step (without it nothing gets uploaded, because the job already failed). Pull the artifact down and run `npx playwright show-trace trace.zip`. The DOM snapshot at the moment of the timeout answers the question directly: the heading is absent, or it is present but a second copy also matched, or the page never left its loading state.

Likely causes, ordered by how often each turns out to be the one:

**Dev server compiling on demand.** If `webServer.command` runs `npm run dev`, the first request to `/dashboard` triggers an on-demand compile. Your local dev server is already warm; CI's is cold, on a two-core runner. Build once and serve the build on CI, and raise `webServer.timeout` to 120000.

**The heading waits on data.** The heading probably renders only after a fetch resolves, and on CI that fetch is slower, so at 5 seconds (Playwright's default `expect` timeout) it is not there yet. The fix is not a longer timeout, it is waiting on the thing you actually mean: `await page.waitForResponse(r => r.url().includes('/api/dashboard') && r.ok())` before the assertion, or asserting on a `data-testid` the component sets only in its loaded state.

**Empty seed data.** If CI starts from a fresh database, the dashboard may render an empty state whose heading text differs. That is a real product path, not a flake.

**Strict mode violation.** `getByRole('heading', { name: /dashboard/i })` throws if it matches two elements. CI's viewport is 1280x720 by default; if you run headed locally in a wider window, a responsive branch can render a second copy of the heading (mobile header plus desktop header) and only CI matches both. The trace makes this obvious, the error reads "resolved to 2 elements."

**Shared state across parallel workers.** If several specs log in as the same user and `fullyParallel` is on, one spec's logout can redirect another off the dashboard. Running CI once with `--workers=1` rules this in or out in a single run.

Reproduce locally instead of debugging through pushes:

```bash
CI=1 npx playwright test tests/dashboard.spec.ts --workers=1 --repeat-each=20
```

If that stays green, run it inside the same container CI uses (`mcr.microsoft.com/playwright:v1.<your-version>-noble`). That closes the remaining gap in browser build, fonts, and CPU count.

Two things not to do: `page.waitForTimeout(3000)` moves the failure rather than removing it, and raising the global expect timeout to 30s just converts a 5-second failure into a 30-second one while hiding the next case.

## 2. Repo structure

I am assuming a TypeScript front-end app with a dashboard UI, inferred from the Playwright suite. Feature-first, with a thin shared layer:

```
src/
  app/            # entry, router, providers, global styles
  features/
    dashboard/
      components/
      api.ts
      hooks.ts
      types.ts
    auth/
  shared/
    ui/           # generic components: Button, Modal
    lib/          # generic helpers: formatDate, http client
    types/
```

One rule holds the whole thing up: a feature may import from `shared/`, never from another feature. Anything two features need gets promoted into `shared/`. The common alternative is layer-only folders (`components/`, `hooks/`, `utils/`), which is fine at small scale but degrades into exactly what you have now, because `components/` becomes the new flat `src/`. Nothing in that scheme tells you where a new file goes.

Moving without losing a week to it:

1. Add a path alias first (`@/*` to `src/*` in `tsconfig.json`, plus the matching alias in your bundler config). After that, moving a file does not rewrite every relative import in the diff.
2. Move one feature per commit using `git mv`, so history follows and `git log --follow <file>` still works. Run the suite after each.
3. Save the largest, most tangled feature for last. By then the shared layer has settled and you will know what belongs in it.
4. Enforce the rule in lint or it drifts back within a month. `eslint-plugin-import`'s `no-restricted-paths`, or `eslint-plugin-boundaries`, turns a cross-feature import into an error.

If `src/` holds more than roughly 150 files, do not do it in one pass. Create `features/` and `shared/`, move only what you touch during normal work, and let the flat area shrink over a few weeks. A half-migrated tree with a clear rule beats a big-bang PR nobody can review.

## What I could not verify

I do not have your repo, your CI logs, or `playwright.config.ts`, so the list above is ordered by frequency in general, not by evidence from your run. I also have not confirmed which framework, runner, or Playwright version you are on, and the structure advice assumes a TS front-end; for a Go or Rust service, or a library, the layout would be different. Paste `playwright.config.ts`, the failing job's output, and the output of `ls src/`, and I can narrow both halves to your actual case.
