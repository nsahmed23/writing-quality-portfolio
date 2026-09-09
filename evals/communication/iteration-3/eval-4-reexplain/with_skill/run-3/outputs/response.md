Run this first, in PowerShell:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

This shows you which program is holding port 8080 right now, at the exact moment `server.ts` tries to use it. The number in its output, labeled `Id`, is that program's PID (short for "process ID"); the steps below call that same number `<PID>`. I don't have access to your machine, `server.ts`, `package.json`, or `nodemon.json`, so I can't guess which program is in the way. This command shows you directly.

On the "why does Node 24 cause this" part: it probably doesn't. That's worth separating out before going further.

EADDRINUSE is the error Windows uses for one simple situation: this port is already taken. Windows raises this error, not Node. It happens at one specific moment: when a program asks Windows to reserve a port for one of its sockets. A socket here just means a program's live claim on a port. That reserving request is called a "bind." If another socket already owns port 8080, Windows refuses the new bind and hands back EADDRINUSE. This whole check happens inside Windows itself, not inside Node. I don't know of anything in Node 24 that changed how that check works.

Here's the distinction that matters: your Node upgrade happened last Thursday, and the errors also started last Thursday. That's two things happening at the same time. On its own, that timing doesn't mean one caused the other. To actually call the Node version the cause, I'd need one of two things: a specific, documented change in Node 24 to how it binds to ports, or a test result, like the errors going away after downgrading to Node 22. I have neither. So I'm not calling Node 24 the cause.

What fits "broke after an upgrade, now fails on every restart" much better is how nodemon restarts your app on Windows.

Here's what happens on every restart. Your app runs inside a separate process that nodemon starts, using a tool called `ts-node`; that separate process is called a "child process." Each time nodemon restarts your app, it first has to kill the old child process. Then it starts a brand new one. The new child process can't bind to port 8080 until the old one is completely gone.

On Unix systems, like Linux and Mac, shutting a process down cleanly uses POSIX signals, a standard, built-in way for one program to tell another one to shut down cleanly. Windows doesn't have real POSIX signals, so nodemon has to fake that same signal on Windows. That fake version is known to be unreliable. When it misfires: the old process is still running when the new one starts. The new one reaches for port 8080, finds the old process still sitting on it, and you get EADDRINUSE.

Here's how that connects to Thursday. Upgrading Node to a new major version almost always forces a full reinstall of your packages (`node_modules`). That reinstall can quietly pull in a different version of `nodemon` or `ts-node` than you had before, without you choosing that. A version change right there is enough to break this shutdown handoff. That's a more direct line from "upgraded Thursday" to "broken since Thursday" than the Node version itself.

Once you've run the command above, here's what its answer tells you to do next:

1. If it shows a `node.exe` process (or something with a similar name): that's the old process still sitting on the port. Kill it with `Stop-Process -Id <PID> -Force`, putting the actual number from the output in place of `<PID>`. Then run `npm run dev` once and check that it starts up clean.
2. If EADDRINUSE comes back again on the next file save, not just this once: that means `server.ts` itself isn't shutting down when nodemon tells it to. Add a shutdown handler. Find whatever variable name you gave to the return value of `app.listen(8080, ...)`, and add this near it:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If the error still comes back after that: update nodemon itself, with `npm install -D nodemon@latest`. Older versions of nodemon have specific, known bugs shutting down process trees on Windows.
4. If the first command showed nothing at all, or showed a process that clearly isn't your app: something outside your code has claimed port 8080. Check for that with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve whole ranges of ports for themselves. If 8080 falls inside one of those ranges, the fix is to pick a different port, or restart the `winnat` service. Either way, it isn't a code change.

If steps 1 to 3 don't hold, there's a more lasting fix: stop using nodemon, and run `tsx watch src/server.ts` instead. tsx keeps a single process running and reloads it in place, instead of killing an old process and starting a new one on every save.

Next: run the command above, then tell me the process name and PID it shows. That decides which of steps 1 to 4 applies.
