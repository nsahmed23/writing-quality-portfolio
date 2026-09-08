3 of your 6 local branches are merged into `main` and safe to delete; 2 are not merged and would be left alone either way.

Merged (would delete):
- `feat/a`
- `feat/b`
- `fix/c`

Not merged (kept; `git branch -d` refuses these regardless):
- `feat/wip1` (1 commit not on main)
- `feat/wip2` (1 commit not on main)

Command:
```
git branch -d feat/a feat/b fix/c
```

Branch deletion isn't easily undone, so I'm confirming before running it rather than just doing it. Reply "yes" and I'll run that command.
