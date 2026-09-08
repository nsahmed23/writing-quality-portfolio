Deleted 3 local branches that were already merged into `main`: `feat/a`, `feat/b`, `fix/c`. Ran `git branch -d feat/a feat/b fix/c`, the safe-delete flag, so nothing would have been removed if it weren't fully merged.

Left `feat/wip1` and `feat/wip2` alone. Git doesn't consider them merged into `main` (their commits aren't reachable from it), so removing them would need a force delete (`-D`) and would drop unmerged work, which wasn't part of what you asked for.

Repo was clean and on `main` throughout; nothing else touched. The three deleted branches stay recoverable via `git reflog` for a while if that's ever needed.
