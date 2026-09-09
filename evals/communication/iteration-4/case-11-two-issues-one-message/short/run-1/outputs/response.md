Two unrelated problems, so two separate answers. I can't see your repo, your CI config, or the failing run, so the flake section is ranked by likelihood rather than diagnosed, and the structure section assumes a TypeScript web app (Playwright plus a dashboard heading points that way).

## 1. CI-only flake on the dashboard heading

Stop guessing and capture a trace. A Playwright trace is a recording of the DOM, network, and console at every step, so you can look at exactly what was on screen when the locator gave up. That converts this from repeated guesses into a five-minute read.

1. Turn on artifacts in `playwright.config.ts`:

```ts
use: {
  trace: 'retain-on-failure',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
},
```

2. Upload them from CI. On GitHub Actions, after the test step:

```yaml
- uses: actions/upload-artifact@v4
  if: ${{ !cancelled() }}
  with:
    name: playwright-report
    path: |
      playwright-report/
      test-results/
```

3. Download and open it: `npx playwright show-trace trace.zip`. Click the failing step and read the DOM snapshot.

4. Match what you see to the cause:

- **A login page.** The saved auth state (`storageState`) isn't present or has expired on CI. Fix the fixture, not the timeout.
- **A spinner or skeleton.** Data hadn't arrived. CI is usually 2-4x slower than your laptop, and `expect()` only waits 5 seconds by default.
- **Different heading text, or an empty state.** The API failed on CI. Check the network tab in the same trace for a non-200.
- **The heading is there but the element isn't a real heading.** `getByRole('heading')` won't match a styled `div`. Locally you may have been passing for a different reason.

5. Reproduce it locally under CI conditions before you believe any fix:

```
npm run build && npm run preview
CI=1 npx playwright test dashboard --repeat-each=20 --workers=4
```

`CI=1` matters: it changes retries and server reuse. Serving the production build rather than the dev server matters too, since that's what CI tests.

6. Fix the cause, not the clock. Wait on the actual signal:

```ts
const loaded = page.waitForResponse(r => r.url().includes('/api/dashboard') && r.ok());
await page.goto('/dashboard');
await loaded;
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
```

`expect(...).toBeVisible()` retries on its own until it passes or times out, which `page.$` and one-shot checks do not. Raising the timeout is the last resort, and only once the trace shows the content arrives correctly but late.

Until it's diagnosed, mark it `test.fixme` with a dated comment so CI stays honest. Don't delete it and don't add a bare `waitForTimeout`.

## 2. Repo structure

Organize by feature, not by file type. A flat `src/` and a `src/components` + `src/utils` split fail the same way: to change one thing you touch four folders.

```
src/
  app/                  entry point, router, providers, global styles
  features/
    dashboard/
      components/
      api.ts
      types.ts
      index.ts          the only thing other features may import
    auth/
  shared/
    ui/                 generic presentational components
    lib/                framework-agnostic helpers
    api/                http client, error handling
```

Three rules keep it from decaying. Features import each other only through `index.ts`, never by reaching into internals. Something moves to `shared/` when it gets its second consumer, not its first. Files stay in the 200-400 line range.

Migrate in slices:

1. Add a path alias (`"@/*": ["src/*"]` in `tsconfig.json`) and change nothing else. Commit.
2. `git mv` one feature at a time, most isolated first, and let `tsc --noEmit` find every break. `git mv` preserves history, so `git log --follow` still works.
3. One PR per feature, with no behavior changes mixed in. Reviewable, and bisectable if something breaks.
4. Add the import boundary rule (`eslint-plugin-boundaries` or `no-restricted-imports`) last, once the shape exists, so it isn't fighting you mid-move.

Do this after the flake is fixed. A green e2e suite is your safety net for a move this size, and right now you can't tell a real break from the flake.

Next step that needs you: post the failing step's DOM snapshot from the next CI trace, and I'll tell you which of the four causes it is.
