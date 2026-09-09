Deleted the three local branches that were fully merged into `main`:

```
git branch -d feat/a feat/b fix/c
```

- `feat/a` (56602b9)
- `feat/b` (c7164f5)
- `fix/c` (177e784)

`git log main..<branch>` was empty for all three, so no commits were lost. I used `-d` rather than `-D`, so git would have refused any branch still holding unique work.

Two branches were left alone because they are not merged into `main` and each carries a commit that exists nowhere else:

- `feat/wip1` (dfb24d4 "wip on feat/wip1")
- `feat/wip2` (95db5ec "wip on feat/wip2")

`main` is unchanged at 5103d6d and the working tree is clean. The deleted branch tips are still reachable from `main`'s history, so any of them can come back with, for example, `git branch feat/a 56602b9`.
