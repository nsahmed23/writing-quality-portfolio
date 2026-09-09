Deleted 3 branches with `git branch -d feat/a feat/b fix/c`. Each was verified merged into `main` first, so no commits were lost; only the branch labels are gone, and the work still lives in `main`'s history.

| Branch | Tip commit | Restore with |
|---|---|---|
| `feat/a` | `0526228` | `git branch feat/a 0526228` |
| `feat/b` | `eea5c8d` | `git branch feat/b eea5c8d` |
| `fix/c` | `68cb5c1` | `git branch fix/c 68cb5c1` |

`main` also shows up in `git branch --merged main` (a branch is always merged into itself), and it is the branch you are on, so it was not touched.

Two branches were left in place because they still have commits that are not in `main`:

- `feat/wip1` (`9a88f97`, 1 commit ahead of main)
- `feat/wip2` (`56367aa`, 1 commit ahead of main)

`git branch -d` refuses these on purpose. Removing them takes `git branch -D`, which throws away those commits, so I did not do it. Tell me if you want them gone and I will run `git branch -D feat/wip1 feat/wip2`.

Next: run `git branch` and confirm the list is now `main`, `feat/wip1`, `feat/wip2`.
