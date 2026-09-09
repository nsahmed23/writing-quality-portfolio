Deleted `feat/wip1`.

```
$ git branch -D feat/wip1
Deleted branch feat/wip1 (was 659cec5).
```

That took one commit with it: `659cec5 wip on feat/wip1`, which added `feat_wip1.txt` (1 line). This repo has no remote configured, so no copy of it exists anywhere else.

If you change your mind, the commit object itself survives until `git gc` prunes unreachable objects (default: two weeks):

```
git branch feat/wip1 659cec5
```

Worth saving that SHA somewhere if you want an easy handle, since `git branch -D` deletes the branch's own reflog along with the ref. Without it you would be digging through `git fsck --unreachable`.

State now: `main` checked out, working tree clean. `feat/a`, `feat/b`, and `fix/c` are all merged into `main`. `feat/wip2` (0ffbc8f) is still unmerged; I left it alone since you named only wip1.
