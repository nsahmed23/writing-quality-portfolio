My previous reply was wrong, and the mistake matters: `git clean -fd` **deletes** untracked files. It does not preview them. The preview command is `git clean -nd`. The only change is one letter, `-n` in place of `-f`.

Here is what each piece means. `-n` means dry run: git prints the list of files it would remove, and removes nothing. `-f` means force, and git refuses to actually delete unless you pass it, which is exactly what made my first version destructive instead of a preview. `-d` means include untracked folders, not just loose files. "Untracked" means git has no record of the file at all: you never ran `git add` on it, and it is in no commit. That is why this deletion is permanent. Git cannot restore a file it never had a copy of.

If you already ran `git clean -fd`, the files it removed are gone from disk, and git cannot bring them back. Your editor's local history or a system backup is the only place left to look.

Run `git clean -nd`, read the list it prints, and decide from there whether anything should actually be deleted.
