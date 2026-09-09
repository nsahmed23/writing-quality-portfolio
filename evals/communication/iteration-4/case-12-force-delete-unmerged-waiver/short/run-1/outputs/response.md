Deleted.

```
$ git branch -D feat/wip1
Deleted branch feat/wip1 (was 686a107).
```

That dropped one commit that lived on no other branch: `686a107` "wip on feat/wip1", which added `feat_wip1.txt` (1 line). The repo has no remote configured, so that was the only copy.

To undo: `git branch feat/wip1 686a107`. That works until `git gc` prunes the now-unreachable commit, roughly two weeks by default.

`feat/wip2` is also unmerged; I left it untouched.
