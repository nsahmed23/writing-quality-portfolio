Run this in PowerShell first:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

This asks Windows one thing: which program is currently sitting on port 8080. Whatever name comes back is the program blocking `server.ts` from starting. I can't check this myself: I don't have access to your machine, to `server.ts`, to `package.json`, or to `nodemon.json`. Running the command is the only way either of us gets a real answer.

Now the plain version of why this error happens at all. Think of a port like a single parking space: only one program can occupy it at a time. When your app starts up and tries to use port 8080, Windows checks whether that space is free. If it's already taken, Windows refuses right away, and that refusal is the error you're seeing, EADDRINUSE. That check happens inside Windows, not inside Node, and nothing I know of in Node 24 changes that check. So Node 24 isn't the thing doing the blocking here; it's just the thing asking Windows for the port and getting turned down.

You asked whether Node 24 is the cause, since the upgrade and the errors both started last Thursday. That timing lines them up, but lining up in time is not the same as one causing the other; that's a sequence, not a cause. To actually call Node 24 the cause, I'd need one of two things: either a specific documented change in Node 24 to how it opens network ports, or a test result showing that going back to Node 22 makes the problem disappear. I have neither. So Node 24 might be involved, but nothing here proves it.

Here's the explanation that fits your symptoms better, broken into plain pieces. You're running nodemon, which restarts your app automatically every time you save a file. Each restart has two steps: stop the old copy, then start a new copy. The old copy has to fully let go of port 8080 before the new copy grabs it. On Windows, that handoff is shakier than it is on Mac or Linux. Mac and Linux have a standard way for one program to tell another "shut down now," called a POSIX signal. Windows has no real equivalent. So nodemon has to fake that signal, and its fake version is known to be unreliable on Windows specifically. There's a second piece that connects this to "last Thursday." Upgrading Node to a new major version almost always means your `node_modules` folder gets wiped and reinstalled. That reinstall can silently pull in a different version of nodemon or ts-node than you had before. A different version can behave differently during that stop-then-start handoff. So the more likely chain is: Node upgrade, then a fresh install, then a different nodemon or ts-node version, then a flakier restart handoff, then your new process colliding with the old one. That chain matches "broke after the upgrade, now fails on every restart" better than Node 24 itself does.

Once you've run the command above, use the result like this:

1. If it returns a `node.exe` process, or something with a similar name: that's the leftover old copy still holding the port. Kill it with `Stop-Process -Id <PID> -Force`, using the actual number the command gave you for `<PID>`. Then run `npm run dev` once and check that it starts cleanly.
2. If EADDRINUSE comes back again the next time you save a file, not just this once: that means `server.ts` isn't shutting down when nodemon tells it to. Find the variable in `server.ts` that holds the result of `app.listen(8080, ...)`, and add this next to it:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If it still keeps happening after that: update nodemon with `npm install -D nodemon@latest`. Older versions of nodemon have specific known bugs around killing process trees on Windows.
4. If the first command returned nothing, or returned a process that clearly isn't your app: something else in Windows has claimed port 8080, and it has nothing to do with your code. Check with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve entire blocks of ports for themselves. If 8080 falls inside one of those blocks, the fix is either a different port or restarting the `winnat` service, not a code change.

If steps 1 through 3 don't fix it for good, there's a sturdier option: drop nodemon and use `tsx watch src/server.ts` instead. tsx keeps one process alive and watching your files, rather than nodemon's approach of killing a process and starting a brand new one on every save.

Next: run the port-check command from the top, and tell me the process name and the PID number it returns. That's what decides which of steps 1 to 4 applies to you.
