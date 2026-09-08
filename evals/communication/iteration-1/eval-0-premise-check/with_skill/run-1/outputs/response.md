Run this first, in PowerShell:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

That shows whatever is actually holding port 8080 the moment `server.ts` tries to bind to it. I don't have access to your machine, `server.ts`, `package.json`, or `nodemon.json`, so this command will tell you more than I can guess from the message alone.

On the "why does Node 24 cause this" part: it probably doesn't, and that's worth separating out before going further. EADDRINUSE is raised by Windows itself, at the moment of the bind call (the OS-level step that reserves a port for a socket), when another socket already owns that port. That check lives in the operating system, not in the Node engine, and I'm not aware of anything Node 24 changed there. The upgrade happening last Thursday and the errors starting last Thursday is a timing match (sequence), not a demonstrated cause; to call the Node version an actual cause I'd want either a specific mechanism (a documented Node 24 change to socket binding) or evidence (for example, downgrading to Node 22 makes it stop), and I have neither.

What fits "broke after an upgrade, now fails on every restart" much better is nodemon's restart handoff on Windows. Each time nodemon restarts your app, it has to kill the old ts-node child process and start a new one before the new one can bind to 8080. Windows doesn't have real POSIX signals (the standard Unix mechanism for telling a process to shut down cleanly), so nodemon has to emulate that handoff on Windows, and the emulation is known to be unreliable: if the old process doesn't actually exit before the new one starts, the new one collides with it and you get EADDRINUSE. A Node major-version upgrade almost always forces a fresh `node_modules` install, which can quietly pull in a different `nodemon` or `ts-node` version and change exactly this handoff behavior. That's a more direct line from "upgraded Thursday" to "broken since Thursday" than the Node version itself being the cause.

Once you've run the command above:

1. If it returns a `node.exe` (or similarly named) process: kill it with `Stop-Process -Id <PID> -Force`, then run `npm run dev` once and confirm it starts clean.
2. If EADDRINUSE comes back on the next file-save restart, not just once, `server.ts` likely isn't exiting when nodemon signals it to stop. Add a shutdown handler, using whatever variable holds the return value of `app.listen(8080, ...)`:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If it still recurs after that, update nodemon: `npm install -D nodemon@latest`. Older nodemon versions have specific, known bugs killing process trees on Windows.
4. If the first command returned nothing, or returned something that isn't your app, check whether Windows itself has claimed the port: `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve blocks of ports, and if 8080 falls inside one of those ranges, the fix is a different port or a `winnat` service restart, not a code change.

If steps 1 to 3 don't hold, the more durable fix is dropping nodemon for `tsx watch src/server.ts`, since tsx manages its own single watched process instead of killing and respawning a separate child.

Next: run the port-check command above and tell me the process name and PID it returns; that decides which of steps 1 to 4 actually applies.
