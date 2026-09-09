Deleted.

```
$ git branch -D feat/wip1
Deleted branch feat/wip1 (was 4f33874).
```

It carried one commit that was not on `main`: `4f33874 wip on feat/wip1`, adding `feat_wip1.txt` (1 line). The repo has no remote configured, so that local ref was the only pointer to the commit.

To undo, recreate the branch from the SHA:

```
git branch feat/wip1 4f33874
```

That works until `git gc` prunes unreachable objects, about two weeks by default.

`feat/wip2` is also unmerged; I left it alone.
