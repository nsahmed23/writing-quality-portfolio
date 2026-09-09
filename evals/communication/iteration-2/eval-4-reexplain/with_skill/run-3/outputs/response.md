Run this command first, in PowerShell:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

This shows you whatever is actually holding onto port 8080 right when `server.ts` tries to grab it. I can't see your machine, your `server.ts`, your `package.json`, or your `nodemon.json`, so this will tell you more than I can guess.

On the "why does Node 24 cause this" part: probably not. Here's the reasoning.

Windows itself raises the EADDRINUSE error, not Node. It happens the instant something tries to grab a port that another program is already holding onto. That check happens inside the operating system, before Node's code even runs. I don't know of anything in Node 24 that changed how that check works.

Here's the distinction that matters: the Node upgrade happened last Thursday, and the errors also started last Thursday. That tells you two things happened at the same time. It doesn't, by itself, tell you one caused the other. To actually call the Node upgrade the cause, I'd need one of two things: a specific, documented change in Node 24 to how it binds to sockets, or a test result, like downgrading to Node 22 and watching the problem disappear. I have neither.

There's a better-fitting explanation: how nodemon restarts your app on Windows.

Every time you save a file, nodemon restarts your app. To do that, it first shuts down the old `ts-node` process. Then it starts a new one. The new process can only grab port 8080 after the old one has fully let go of it. On Linux and Mac, there's a standard, reliable way for one process to tell another to shut down cleanly, called a POSIX signal. Windows doesn't have that same mechanism, so nodemon has to fake the same effect, and the fake version is known to be unreliable. When the old process is slow to exit, the new one starts anyway. It tries to grab port 8080 while the old one is still holding it. That collision is what EADDRINUSE means.

This also explains why the problem started right after the upgrade, just not because of Node itself. Upgrading Node's major version almost always means deleting `node_modules` and reinstalling everything from scratch. That reinstall can quietly pull in a different version of `nodemon` or `ts-node` than you had before. A version change in either one can change exactly this shutdown-and-restart behavior. So the real chain is: upgrade, then a fresh `node_modules` install, then a different `nodemon` or `ts-node` version, then different restart behavior, then EADDRINUSE. That's a more direct line from last Thursday's upgrade to last Thursday's errors than blaming Node 24 itself.

Once you've run the command above, here's what to do with the result:

1. If it shows a `node.exe` process (or something with a similar name): that's your own old server, still holding the port. Stop it with `Stop-Process -Id <PID> -Force`, using the actual number the command gave you in place of `<PID>`. Then run `npm run dev` once and check that it starts cleanly.
2. If EADDRINUSE keeps coming back on every file-save restart, not just this once: `server.ts` isn't exiting when nodemon tells it to stop. Add a shutdown handler, using whatever variable name your code already gives to the return value of `app.listen(8080, ...)`:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If it still comes back after that: update nodemon itself, with `npm install -D nodemon@latest`. Older versions of nodemon have specific, known bugs in how they kill process trees on Windows.
4. If the first command returned nothing, or returned something that clearly isn't your app: something else on Windows has claimed port 8080, not your code. Check with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve whole blocks of ports for themselves. If 8080 falls inside one of those blocks, the fix is a different port, or restarting the `winnat` service, not a code change.

If steps 1 to 3 don't hold, the fix that actually lasts is replacing nodemon with `tsx watch src/server.ts`. tsx manages one single process the whole time, instead of killing an old one and spawning a separate new one the way nodemon does, so this exact collision can't happen.

Run the command at the top and tell me two things: the process name, and the PID number it returns. That answer decides which of steps 1 to 4 applies to you.
