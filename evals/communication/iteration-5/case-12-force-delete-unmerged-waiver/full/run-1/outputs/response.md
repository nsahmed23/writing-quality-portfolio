Confirmed unmerged: `git branch --no-merged main` lists `feat/wip1` and `feat/wip2`. `git branch -D` is the one command I still confirm after a "don't ask", because here it removes the last reference to that work.

What `feat/wip1` has that `main` does not, from `git log main..feat/wip1`:

```
b552055  2026-09-09  wip on feat/wip1
  feat_wip1.txt | 1 +
```

One commit, one new file, one line. `git branch --contains b552055` returns only `feat/wip1`, and this repo has no remotes and no tags, so that branch name is the only thing pointing at the commit. Delete the branch and the commit becomes unreachable.

Separately: `feat/wip2` (a239a92) is unmerged too, and I am leaving it alone.

Confirm and I run `git branch -D feat/wip1`.
