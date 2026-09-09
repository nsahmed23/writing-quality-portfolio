Run this first, in PowerShell:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

This tells you whatever program is holding port 8080 right when `server.ts` tries to start using it. I don't have access to your machine, your `server.ts`, your `package.json`, or your `nodemon.json`. That means this command can tell you more than I can guess from your message alone.

On whether Node 24 is actually the cause: probably not. EADDRINUSE comes from Windows, not from Node. It fires at one specific moment: when a program's connection endpoint, called a socket, tries to claim a port for itself. That moment is called a "bind." Windows raises EADDRINUSE when a bind can't happen. That happens when another socket already has that same port. That check happens inside the operating system, not inside the Node engine. I'm not aware of anything in Node 24 that changed this. The Node upgrade happened last Thursday. The errors started last Thursday too. But that's only a timing match, two things happening close together. A timing match is not the same as proof that one caused the other. To actually call Node 24 the cause, I'd need one of two things: a documented Node 24 change to how sockets bind to ports, or a test, such as downgrading to Node 22 and watching the errors stop. I have neither.

A better fit for "broke after an upgrade, now happens on every restart" is something called nodemon's restart handoff. Nodemon is the tool restarting your server each time you save a file. On every restart, it kills the old ts-node child process, then starts a new one. The new one has to finish starting before it can bind to port 8080. On Windows, there's a problem with the "kill it" step. Unix systems, meaning Mac and Linux, have a standard way to tell a running program to shut down cleanly. That's called a POSIX signal. Windows doesn't have a real version of that. Nodemon has to fake it on Windows. That fake version is known to be unreliable. If the old process hasn't actually finished exiting by the time the new one starts, the two collide over port 8080. That collision is your EADDRINUSE. There's also a reason this likely started specifically last Thursday: a Node major-version upgrade almost always forces a full reinstall of `node_modules`. That reinstall can quietly pull in a different version of nodemon, or a different version of ts-node, than you had before. A different version can change exactly this restart-and-kill behavior. That connects "upgraded Thursday" to "broken since Thursday" more directly than blaming the Node version itself.

Once you have the process name and PID (process ID) from the command above:

1. If it's a node.exe process (or something with a similar name): kill it with `Stop-Process -Id <PID> -Force`. Then run `npm run dev` once and check that it starts clean.
2. If EADDRINUSE keeps coming back on every file-save restart, not just once: `server.ts` likely isn't exiting when nodemon tells it to stop. Add a shutdown handler. Find whatever variable holds the result of `app.listen(8080, ...)`. Add this code next to it:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If it still keeps happening after that: update nodemon by running `npm install -D nodemon@latest`. Older nodemon versions have specific, known bugs killing process trees on Windows.
4. If the first command returned nothing, or returned a process that isn't your app: something else on Windows has claimed the port. Check with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve blocks of ports for themselves. If 8080 falls inside one of those blocks, the fix is a different port or restarting the winnat service. It is not a code change.

If steps 1 through 3 don't fix it for good, the sturdier long-term fix is replacing nodemon with `tsx watch src/server.ts`. tsx keeps one single process running. It just restarts that same process, instead of killing one process and spawning a separate new one. That removes the handoff gap causing this in the first place.

Next: run the command at the top, and tell me the process name and PID it returns.
