Correction first, because my last message was wrong in the dangerous direction: `git clean -fd` **deletes** untracked files. It does not preview them. Don't run it.

The preview command is:

```
git clean -nd
```

The flags read as words:

- `-n`: dry run. Print what *would* be deleted, delete nothing.
- `-d`: include whole directories, not just loose files.
- `-f`: force. Actually delete. Git requires this flag, so you can't wipe files by typing `git clean` on its own.

So `-nd` shows you the list, and `-fd` carries it out.

Use it in two steps:

1. Run `git clean -nd` and read the output. Every line is a file that would be destroyed.
2. If that list is exactly what you want gone, run `git clean -fd`.

One thing worth knowing before step 2: "untracked" means git has never stored a copy of that file, so once it's deleted git cannot bring it back. There is no undo, and no `stash` or `reset` that helps. Files matched by `.gitignore` are safe from plain `git clean -fd` (it skips them); only `git clean -fdx` removes those too.

If you already ran `git clean -fd` because I told you to, tell me what was in the folder. Recovery would have to come from your editor's local history (VS Code keeps one in the Timeline panel) or an OS-level backup, not from git.
