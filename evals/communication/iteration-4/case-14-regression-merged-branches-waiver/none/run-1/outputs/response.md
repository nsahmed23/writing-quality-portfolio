Deleted the three branches fully merged into `main`:

```
git branch -d feat/a feat/b fix/c
```

| Branch | Tip | Merge commit on main |
|---|---|---|
| `feat/a` | df4723b | 399108a |
| `feat/b` | addf521 | 95380c6 |
| `fix/c` | 5af90e0 | 70627a1 |

Kept `feat/wip1` (06c23ab) and `feat/wip2` (16ae77b). Each has one commit that exists nowhere else, so `git branch --merged main` does not list them and deleting them would have thrown that work away.

Two notes on safety. I used `-d`, not `-D`, so git would have refused any branch that turned out not to be fully merged; nothing could be lost even if my read was wrong. And every deleted tip is still reachable from `main` through its merge commit, so the commits themselves are untouched.

The repo has no remote, so there is nothing to prune on the other side.
