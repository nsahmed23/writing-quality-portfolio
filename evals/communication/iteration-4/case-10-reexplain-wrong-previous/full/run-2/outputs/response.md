Correction first: `git clean -fd` does not preview anything. It deletes untracked files and folders immediately. The command that previews is `git clean -nd`. The change is one letter, `-f` becomes `-n`.

Untracked files are files sitting in your project folder that Git is not watching. You never ran `git add` on them, so Git holds no copy of them.

The letters after `git clean` are switches that change what the command does. `-n` means dry run: Git prints what it would remove, and removes nothing. `-d` means include folders, not only loose files. `-f` means force: Git actually performs the deletion.

Git insists on `-f` before it will delete, because it cannot undo this. Those files were never saved into Git, so there is no earlier version to restore.

`git clean -nd` prints a list like this and changes nothing on disk:

```
Would remove notes.txt
Would remove build/
```

If every line in that list is something you are willing to lose, `git clean -fd` is the command that removes them.

Next: run `git clean -nd` and read the list.
