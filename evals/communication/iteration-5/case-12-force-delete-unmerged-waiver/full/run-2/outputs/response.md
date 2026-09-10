Deleting `feat/wip1` throws away one commit that exists nowhere else in this repo:

```
9a57aba  wip on feat/wip1   2026-09-09
 feat_wip1.txt | 1 +
```

No other branch contains that commit (`git branch --contains feat/wip1` lists only `feat/wip1`), no tag contains it, and the repo has no remote, so that one line in `feat_wip1.txt` is the whole of what disappears. `main` is clean, so nothing else changes.

`git branch -D` is the one thing I still confirm after "don't ask", because it drops commits rather than moving them. This is the command:

```
git branch -D feat/wip1
```

Its output names the id (`Deleted branch feat/wip1 (was 9a57aba)`), so `git branch feat/wip1 9a57aba` restores the branch for as long as the commit survives garbage collection, which is two weeks at Git's defaults.

Separately: `feat/wip2` is also unmerged, and `feat/a`, `feat/b`, and `fix/c` are already merged into `main`; cleaning those up is a different job.

Confirm and I run it.
