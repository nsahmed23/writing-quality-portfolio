Run this in PowerShell (the same command as before):

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

This asks Windows one thing: which program is holding port 8080 right now. Port 8080 is the address your server grabs when it starts up. Programmers call that grabbing step "binding." If another program already grabbed port 8080 first, your server can't bind, and that's your error.

I can't see your computer. I also can't see your `server.ts`, `package.json`, or `nodemon.json` files. So instead of guessing which program is in the way, this command checks the real answer directly.

Now the "does Node 24 cause this" question, in plainer terms. EADDRINUSE is not a Node error. It's a Windows error. Windows raises it at the exact moment a program tries to bind to a port that something else already holds. Node just reports what Windows already decided; it isn't the one making that call. As far as I know, nothing in Node 24 changed how binding works.

Here's why I'm being careful about blaming Node 24. You upgraded to Node 24 last Thursday. Your errors started last Thursday too. Those two things happening on the same day is not proof that one caused the other. It's just a matching timeline. To actually blame Node 24, I'd need one of two things: a specific documented change in Node 24 to how it binds to ports, or a test result, like downgrading to Node 22 and watching the problem disappear. I have neither. So I'm not blaming Node 24 yet.

Here's the pattern that actually matches what you're seeing: it broke after the upgrade, and now it fails on every restart. That pattern points at nodemon's restart handoff on Windows, not at Node itself.

Here's what that handoff means. Every time you save a file, nodemon has to shut down your old running server and start a new one in its place. The new one needs port 8080. The old one has to let go of port 8080 first. On Mac or Linux, there's a clean, standard way for one program to tell another "shut down now"; that's called a POSIX signal. Windows doesn't have that same mechanism. So nodemon has to fake it, and the fake version is known to be unreliable. Picture two cars pulling into the same parking spot: nodemon waves the first car out and waves the second one in, but if the first car is still pulling out when the second one pulls forward, they collide. That collision is your EADDRINUSE error.

Here's how Thursday's upgrade still connects to your problem, even though Node 24 itself probably isn't the cause. Upgrading Node's major version almost always forces your project to delete and reinstall its `node_modules` folder from scratch. That fresh install can quietly pull in a different version of `nodemon`, or a different version of `ts-node`, than you had before. A different version of either one can behave differently at exactly this handoff moment. So the Node upgrade is connected to your problem, but most likely as the trigger that changed some other tool's version, not as a direct cause on its own.

Once you've run the command at the top, here's what its answer tells you to do next:

1. If it shows a process called `node.exe` (or something similarly named): stop that process with `Stop-Process -Id <PID> -Force`, using the process ID number the command gave you. Then run `npm run dev` once and check that it starts without the error.
2. If the error comes back again the next time you save a file, not just this once: your `server.ts` file is probably not shutting itself down when nodemon tells it to. Fix that by adding a shutdown handler. Find whatever variable in `server.ts` holds the result of `app.listen(8080, ...)`, and add this:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
3. If the error still keeps coming back after that: update nodemon itself, with `npm install -D nodemon@latest`. Older versions of nodemon have specific, known bugs on Windows where they fail to fully shut down a process tree (a running program plus every smaller process it started).
4. If the very first command showed nothing at all, or showed some process that clearly isn't your app: something else on Windows has already claimed port 8080, not your code. Check that with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V are all known to reserve whole blocks of ports for themselves. If port 8080 falls inside one of those reserved blocks, the fix is either a different port or restarting the `winnat` Windows service, not a code change.

If steps 1 through 3 don't fix it for good, there's a more permanent option: replace nodemon with `tsx watch src/server.ts`. tsx watches and restarts your one server process directly, instead of nodemon's approach of killing one process and starting a separate new one in its place.

Next: run the command at the top, and tell me the process name and the process ID number it gives back. That answer decides which of steps 1 through 4 applies to you.