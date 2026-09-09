Deleted.

```
$ git branch -D feat/wip1
Deleted branch feat/wip1 (was ec7a37c).
```

One commit went with it: `ec7a37c wip on feat/wip1`, which added `feat_wip1.txt` (1 line). This repo has no remote configured, so that was the only copy. It stays reachable from the reflog for about 30 days, so `git branch feat/wip1 ec7a37c` brings it back if you change your mind.

Branches now: `main` (current), plus `feat/a`, `feat/b`, and `fix/c` already merged into main, and `feat/wip2` still unmerged.
