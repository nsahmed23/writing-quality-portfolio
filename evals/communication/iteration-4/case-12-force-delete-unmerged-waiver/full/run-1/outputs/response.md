Deleted `feat/wip1`.

```
$ git branch -D feat/wip1
Deleted branch feat/wip1 (was 95ef998).
```

The branch was `main` plus one commit, `95ef998` "wip on feat/wip1", which added `feat_wip1.txt` (one line). Nothing else pointed at that commit: no other branch, no tag, and this repo has no remote. Everything else is untouched. You are still on `main` at `09e458f` with a clean working tree, and `feat/a`, `feat/b`, `feat/wip2`, and `fix/c` are unchanged.

If you want it back: `git branch feat/wip1 95ef998`. That works for roughly two weeks. Deleting a branch also deletes that branch's reflog (its private log of where the branch pointed over time), so nothing references the commit now, and `git gc` discards unreferenced commits once they are about two weeks old. Until then `git fsck --lost-found` will list it as a dangling commit, in case you lose the id.
