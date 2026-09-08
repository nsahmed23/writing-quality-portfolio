Run `netstat -ano | findstr :8080` to see which process is holding the port (EADDRINUSE means Node tried to bind to a port the OS says is already taken); that takes about 10 seconds and tells you immediately whether a leftover process is the real problem.

1. Note the PID (process ID) in the last column of the output.
2. Run `tasklist /FI "PID eq <pid>"`. If it's a leftover `node.exe`, that's the previous restart's process, still holding the port.
3. Kill it with `taskkill /PID <pid> /F`, then run `npm run dev` again.

If nothing shows up on port 8080 in step 1, the conflict isn't nodemon at all, it's a second process. Run `tasklist | findstr node` to check for another `npm run dev` still running in a different terminal, or a Docker container mapped to 8080.

On "why does Node 24 cause this": I don't have evidence that it does. You upgraded Thursday and the errors started after that, but "after" isn't "because of," that's a timing match, not a demonstrated cause. I can't see `server.ts`, `package.json`, or your running processes, so I can't confirm what actually changed. What I can tell you is what produces this error on every restart, and it applies at any Node version, which makes it the more likely explanation:

nodemon runs `ts-node` against `server.ts` as a child process. On every restart it kills that child and starts a new one, and the new one only succeeds once the OS has freed port 8080. On Windows, fully terminating that child process is less reliable than on Linux or Mac, a known rough edge for nodemon there, and Windows is generally stricter than POSIX about letting a new process rebind a port the instant the old one exits. If the old process doesn't fully exit, or exits without your code closing its own listener, port 8080 stays bound for a beat and the next `server.listen(8080)` throws EADDRINUSE.

Two things could plausibly have changed Thursday that aren't Node 24 itself:

1. If you reinstalled `node_modules` when you switched versions, and `package.json` uses caret ranges (`^3.0.0`, meaning npm can install any newer minor or patch version), `npm install` may have pulled a newer nodemon or ts-node without you choosing to upgrade them directly. A version bump in either tool can change restart timing. Run `npm ls nodemon ts-node` to see what's actually installed now.
2. If `server.ts` never handled shutdown signals, the process was already relying on the OS to release the socket fast enough on exit. That was always a race, and small differences in machine timing are enough to tip it from usually fine to failing on every restart.

To stop this recurring rather than just clearing it once, close the server explicitly on shutdown. Adapt `app.listen` below to whatever `server.ts` actually uses; I haven't seen the file:

```ts
const server = app.listen(8080, () => console.log('listening on 8080'));

process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
});
```

If restarts are still occasionally racy after that, add a restart delay: either `--delay 1` on the `nodemon` command in your `dev` script, or `"delay": "1000"` in `nodemon.json` if you use one. Either gives the old process a full second to release the port before nodemon starts the new one.

Next: run the netstat command above and check whether the PID belongs to an old `node.exe`.
