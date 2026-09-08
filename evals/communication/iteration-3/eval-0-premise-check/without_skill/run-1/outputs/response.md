Node 24 itself isn't a known cause of EADDRINUSE. That error just means something is already bound to port 8080 when your server tries to `listen()`, and I'm not aware of any Node version change that touches TCP port-binding behavior in a way that would produce it. The timing (upgraded Thursday, broken on every restart since) is worth taking seriously as a clue, but it's more likely that the upgrade triggered this indirectly than that Node 24 causes it directly. I can't confirm which from here since I don't have access to your machine or repo, so treat the rest of this as diagnosis, not a confirmed root cause.

Given it fails on every restart rather than just the first start, the two usual suspects for this exact pattern are:

1. **A leftover process is still holding 8080 when nodemon restarts.** nodemon runs ts-node as a child process, and on Windows it has to tear that down with `taskkill` instead of a clean POSIX signal. If the old process (or something ts-node spawned) hasn't fully exited before nodemon starts the replacement, the new bind fails.
2. **The socket is briefly stuck in TIME_WAIT after the old process exits.** This is a known Windows/Node quirk: even a clean shutdown can leave the port unusable for a short window afterward, and if nodemon restarts fast enough (e.g., on every file save), it can hit that window.

Where the Node 24 upgrade plausibly fits in: switching Node versions usually means `node_modules` got reinstalled or nodemon/ts-node picked up newer versions along the way, which can change how child processes are spawned and torn down. It's also easy for an old terminal or editor-integrated shell to still have a pre-upgrade node process alive in the background, quietly sitting on 8080, after you moved to Node 24 in a new shell. Either would produce exactly this symptom without Node 24 being the actual mechanism.

To see what's actually on the port, in PowerShell:

```
netstat -ano | findstr :8080
```

The last column is a PID. Then:

```
Get-Process -Id <PID>
```

to identify it, and if it's a stray node/ts-node process:

```
Stop-Process -Id <PID> -Force
```

If you watch Task Manager across a couple of restarts and see node.exe entries piling up instead of being replaced, that confirms it's leftover-process cleanup, not Node 24 itself.

A few things worth trying once that's confirmed:

- Update nodemon to its latest version; Windows process-kill reliability has improved across releases, and it's worth checking whatever `nodemon.json` or the `nodemon` block in `package.json` your `dev` script uses.
- Add a restart delay (nodemon has a `--delay` option, settable in `nodemon.json` too) to give Windows a moment to fully release the socket before the next bind.
- Make sure `server.ts` actually closes the HTTP server on shutdown (`process.on('SIGINT', ...)` / `process.on('SIGTERM', ...)` calling `server.close()`), so restarts release 8080 cleanly instead of leaving it half torn down.
- As a blunt sanity check, run `taskkill /IM node.exe /F` to clear everything, then `npm run dev` once from a cold start. If that first run is clean, the bug is in restart cleanup, not the initial bind.
- Worth a glance: 8080 is a very common default port, so double check nothing unrelated (another project, a proxy, some other dev tool) grabbed it around the same time.

What I can't verify without your machine: what netstat actually shows on port 8080, your installed nodemon/ts-node versions, whether `server.ts` has a shutdown handler, and what's in your nodemon config. The netstat command above is the fastest way to settle whether this is a leftover process, a TIME_WAIT window, or something else entirely.
