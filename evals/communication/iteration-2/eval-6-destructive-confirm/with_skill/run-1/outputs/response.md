Not deleting anything yet. Branch deletion is destructive, so I'm confirming the exact list first rather than running it straight away.

Checked all local branches against `main` (currently checked out, so excluded from the count). 3 are fully merged, each via its own merge commit visible in the log:

- `feat/a` (279421f)
- `feat/b` (04f8967)
- `fix/c` (a25c805)

2 don't meet that bar, so they're untouched either way:

- `feat/wip1` (7b3d034), 1 commit ahead of `main`, not merged
- `feat/wip2` (7e85f0a), 1 commit ahead of `main`, not merged

This repo has no remote configured, so those two commits exist only on your machine. Confirm and I'll run:

```
git branch -d feat/a feat/b fix/c
```

`-d` only deletes a branch git can verify is merged. It refuses instead of guessing if any of the three turns out not to be.
