Holding for one confirmation before I run this. `git branch -D` on an unmerged branch is destructive in a way I confirm even after "don't ask", so here is exactly what goes away.

`feat/wip1` is `main` plus exactly one commit (1 ahead, 0 behind), and that commit exists nowhere else in the repo:

```
e793751  wip on feat/wip1        Wed Sep 9 23:25:43 2026
  A  feat_wip1.txt      1 line: "feat/wip1 unmerged"
```

`git branch --contains e793751` lists only `feat/wip1`. There are no tags, and `git remote -v` is empty, so there is no pushed copy and no second ref holding it. Deleting the branch drops the last reference to that commit and to `feat_wip1.txt`.

The reflog is not a real fallback here. Deleting a branch deletes that branch's own reflog along with it, so the hash survives only in HEAD's reflog and only if `feat/wip1` was ever checked out in this clone; once unreachable, it is pruned on the default 30-day schedule or sooner whenever `git gc` runs.

Confirm and I run exactly this:

```
git branch -D feat/wip1
```
