Correction first, because the simpler explanation would have been an explanation of the wrong command. `git clean -fd` does not preview anything. It deletes untracked files right away, and because git never had copies of them, there is no undo. Don't run it yet.

The preview command is:

```
git clean -nd
```

That prints a list of what would be deleted and changes nothing on disk.

What the letters mean:

- `-n` is dry run: show me, don't do it.
- `-d` includes untracked folders, not just loose files.
- `-f` is force: actually delete. `-f` and `-n` are opposites, so you use one or the other, never both.

"Untracked" means files git has never been told about: build output, scratch files, anything you made but never ran `git add` on. Anything you have committed is safe from `git clean` either way.

One gap in that preview: by default it skips files ignored by `.gitignore`, such as `node_modules/` or a local `.env`. Add `-x` to see those too (`git clean -ndx`). That is the flag that eats `.env` files, so read the list closely before acting on it.

When the preview lists only things you are happy to lose, swap `-n` for `-f` to do it for real:

```
git clean -fd
```
