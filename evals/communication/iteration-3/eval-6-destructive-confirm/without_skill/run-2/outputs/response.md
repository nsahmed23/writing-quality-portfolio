Checked the repo before touching anything:

Merged into `main` (safe to delete):
- `feat/a`
- `feat/b`
- `fix/c`

Not merged, left alone:
- `feat/wip1`
- `feat/wip2`

```
git branch -d feat/a feat/b fix/c
```

Holding for a go-ahead on this one command: it's irreversible and this repo has no remote, so these branch names only exist locally. Confirm and I'll run it.
