First, a correction: my earlier answer was wrong, and wrong in a way that could cost you files. `git clean -fd` **deletes** untracked files. It does not preview anything. If you already ran it, those files are gone; git clean removes them outright rather than sending them to a recycle bin.

The preview command is:

```
git clean -nd
```

The pieces:

- An **untracked file** is one sitting in your project folder that git has never been told to manage, meaning you have never run `git add` on it. Build output, log files, a scratch script you wrote yesterday.
- `-n` is "dry run": print what would be deleted, delete nothing.
- `-d` means "look inside untracked folders too", not just loose files at the top level.
- `-f` is "force", and it is the flag that actually performs the deletion. `-n` and `-f` are opposites, and I handed you the deleting one.

So it is two steps:

1. Run `git clean -nd` and read the list. Each line is a file that would be removed.
2. If the list looks right, run `git clean -fd` to remove them for real.

One thing worth knowing: files matched by `.gitignore` are skipped by both commands unless you add `-x`. That is usually what you want, since it keeps `node_modules` and `.env` out of it.
