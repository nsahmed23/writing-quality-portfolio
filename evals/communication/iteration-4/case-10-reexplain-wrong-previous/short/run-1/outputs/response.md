Correction first, because my last reply was wrong: `git clean -fd` does not preview anything. It permanently deletes untracked files and directories, with no undo. Do not run it yet.

The preview version swaps `-f` for `-n`:

```
git clean -nd
```

What the flags mean:

- `-n` is a dry run. It prints what would be removed and removes nothing.
- `-d` includes untracked directories, not just loose files.
- `-f` means "force", and it is the flag that actually does the deleting. Git requires it because the deletion cannot be undone.

"Untracked" means a file Git has never been asked to store: it sits in your folder, but you never ran `git add` on it and it appears in no commit. That is why deleting it is final. There is no saved copy to restore from.

So the safe order is: run `git clean -nd`, read the list it prints, and only run `git clean -fd` if every line on that list is something you genuinely want gone. If something on the list should stay, move it out of the folder first, or add it to `.gitignore` (files matched by `.gitignore` are skipped by `git clean` unless you also pass `-x`).
