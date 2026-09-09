Deleted: `git branch -D feat/wip1` (was 28a1757).

What went with it: one commit, `28a1757 wip on feat/wip1`, which added `feat_wip1.txt` (1 line). No other branch contained that commit and this repo has no remote configured, so that work now exists nowhere else. Nothing else changed: `main` is still at 088daf6 with a clean working tree, and feat/a, feat/b, and fix/c remain merged into main.

To undo: `git branch feat/wip1 28a1757`. That works while the commit object is still in the repository. Deleting a branch drops its reflog, so the commit is now unreachable, and Git prunes unreachable objects roughly two weeks after they become unreachable, the next time garbage collection runs. Running `git gc --prune=now` closes that window immediately.

Separately: `feat/wip2` (51c3a37, one commit adding `feat_wip2.txt`) is also unmerged into main. Delete that one too?
