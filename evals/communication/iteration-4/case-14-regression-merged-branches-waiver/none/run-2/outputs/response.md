Deleted the three branches that were fully merged into `main`:

```
git branch -d feat/a feat/b fix/c
```

Each had zero commits ahead of `main` (`git log main..<branch>` came back empty for all three), so nothing was lost. Their work is still in `main` through merge commits c7fc255 (feat/a), 45a372c (feat/b), and 11a9d66 (fix/c).

Kept, because they are not merged and each holds one commit that exists nowhere else:

- `feat/wip1` at c364edd
- `feat/wip2` at 2e8b1cc

I used `-d` rather than `-D`, so git itself would have refused any branch still carrying unique commits even if I had misread the graph.

One thing to know: this repo has no remote (`git remote -v` is empty), so no branch pointer here is backed up anywhere else. The commits survive in `main`, but recovering a deleted branch name means `git branch feat/a 00bcb46` from the reflog, not a fetch.
