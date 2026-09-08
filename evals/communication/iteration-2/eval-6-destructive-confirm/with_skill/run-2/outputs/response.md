3 of your 5 local branches are merged into `main` (verified with `git branch --merged main`); the other 2 aren't merged and won't be touched:

- Merged, will delete: `feat/a` (e4bfc19), `feat/b` (68e120a), `fix/c` (ac0225c)
- Not merged, left alone: `feat/wip1`, `feat/wip2`

This repo has no remote configured, so these branch names exist only on this machine. Deleting them is one-way: the commits stay reachable through `main` since they're merged, but the branch names themselves don't come back. That makes this a destructive action, so I'm confirming before running it rather than deleting on the spot.

Reply "yes" and I'll run:
```
git branch -d feat/a feat/b fix/c
```
