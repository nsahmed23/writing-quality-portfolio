Done. Deleted the three local branches that were already merged into `main`:

```
Deleted branch feat/a (was 21ddd2a).
Deleted branch feat/b (was 6931469).
Deleted branch fix/c (was 1792e89).
```

The command, run from the repo root:

```bash
git branch -d feat/a feat/b fix/c
```

I used `-d` rather than `-D` so git would have refused anything that turned out not to be fully merged.

Two branches are still there, because they are not merged into `main`:

- `feat/wip1` at f3d8c1c
- `feat/wip2` at cf2eb6b

Each carries one commit that exists nowhere else. Deleting those would take `git branch -D`, and the commits would then survive only in the reflog.

Nothing else changed. You are still on `main` at 0d200e3 with a clean working tree, and the repo has no remotes, so there was nothing to prune or push. If you want any of the three back, `git branch feat/a 21ddd2a` recreates it; all three commits are still reachable from `main`, so nothing was lost.
