Deleted the three branches that were fully merged into `main`:

```
git branch -d feat/a feat/b fix/c
```

Tip commits, in case you want any of them back: `feat/a` was 91e26b2, `feat/b` was d00c673, `fix/c` was 8643cd1. Restore one with `git branch feat/a 91e26b2`. Nothing was lost either way; all three commits are still reachable from `main` through the merge commits 6395ffd, 2bcb0ab, and 52f595f.

Kept `feat/wip1` and `feat/wip2`. Each still holds one commit that is not in `main` (6e16977 and 4dc7a17), so they are not merged and `git branch -d` would have refused them.

Check with `git branch`: you should now see `feat/wip1`, `feat/wip2`, and `main`.
