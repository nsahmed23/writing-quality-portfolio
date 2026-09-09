Run this first, in PowerShell:

```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue).OwningProcess
```

Here's what that does, in plain terms. It asks Windows one question: which program is currently holding onto port 8080? Run it right when you're hitting the error, and Windows answers back with that program's name and its PID (process ID, just a number Windows uses to track a running program). I can't see your machine, your `server.ts`, your `package.json`, or your `nodemon.json`, so I can't look this up myself. Running the command gets you a real answer instead of my guess.

Now, the question of whether Node 24 is the cause. Short version: probably not, and it's worth slowing down on that before doing anything else.

The error you're seeing, EADDRINUSE, is Windows' way of saying "this port is already being used." Windows raises that error at one specific moment: when a program asks to grab a port for itself (this is called "binding" to the port), and some other program already has that same port. That check happens inside Windows, not inside Node. Node is only the thing doing the asking. I don't know of anything that changed in Node 24 about how it does that asking.

Here's the distinction that matters. You upgraded Node last Thursday, and the errors started last Thursday. That timing is real. But "happened at the same time" is not the same claim as "one caused the other," it's a coincidence in timing until something stronger backs it up. To actually call Node 24 the cause, I'd need one of two things: a specific, documented change in Node 24 to how it binds to ports, or a test result, like the errors going away after you downgrade to Node 22. Right now I have neither.

Here's an explanation that fits your situation better: it broke right after the upgrade, and now it fails on every restart. That pattern points at nodemon, specifically at how nodemon restarts your app on Windows.

Every time nodemon restarts your app, two things have to happen in order. First, it kills the old copy of your server, which is running through ts-node. Second, it starts a brand new copy. The new copy can only grab port 8080 once the old copy has fully let go of it. Picture two cars and one parking spot: the second car can only pull in once the first car has actually driven away, not just started to leave.

On Mac and Linux, there's a clean, standard way for one program to tell another "shut down now, and let me know once you actually have"; that mechanism is called a POSIX signal. Windows does not have a real version of that mechanism, so nodemon has to fake it, and the fake version is known to be unreliable. When the old server process is slow to exit, or never exits, the new copy starts anyway, tries to grab port 8080, and runs straight into the old process still sitting on it. That collision is what produces EADDRINUSE.

Here's how this connects back to the Node 24 upgrade. Bumping a major Node version almost always means running a fresh install of your dependencies, a fresh `node_modules` folder. That fresh install can quietly bring in a different version of `nodemon` or `ts-node` than you had before, even though you never chose to change either one. A version change in either tool can change exactly this restart handoff. So the more direct line from "upgraded last Thursday" to "broken since Thursday" runs through nodemon and ts-node quietly changing versions, not through Node 24 itself.

Once you've run the command at the top, here's what each possible result means, in order.

1. If it returns a `node.exe` process, or something with a similar name: that's the old server, still sitting on the port. Kill it with `Stop-Process -Id <PID> -Force`, putting the actual number you got back in place of `<PID>`. Then run `npm run dev` by itself, once, and check that it starts cleanly.
2. If that fixes it once, but EADDRINUSE comes back the next time you save a file and nodemon restarts: `server.ts` is not shutting down when nodemon tells it to stop. The fix is to add a shutdown handler. In `server.ts`, find the variable that holds the result of `app.listen(8080, ...)`. The code below assumes that variable is named `server`; if yours has a different name, use that name instead. Add this:
   ```ts
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```
   In plain terms, this tells your server: the moment you're told to stop, close the port first, and only then exit.
3. If EADDRINUSE still comes back after that: update nodemon itself, with `npm install -D nodemon@latest`. Older versions of nodemon have specific, known bugs in how they kill process trees on Windows.
4. If the very first command returned nothing at all, or returned something that clearly isn't your app: the port might be claimed by Windows itself, not by your code. Check that with `netsh interface ipv4 show excludedportrange protocol=tcp`. Docker Desktop, WSL2, and Hyper-V can each reserve whole ranges of ports for their own use. If 8080 falls inside one of those reserved ranges, the fix is a different port, or a restart of the `winnat` service; changing your code would not help.

If steps 1 through 3 don't hold, meaning the problem keeps coming back no matter what you try: consider replacing nodemon with `tsx watch src/server.ts` instead. The reason that's more durable: tsx keeps one single process running and reloads your code inside it, rather than nodemon's approach of killing a whole process and starting a separate new one each time. With no separate process to hand off to, there's nothing left to collide with.

Next: run the command at the top, and tell me the process name and the PID number it returns. That result decides which of steps 1 through 4 actually applies to you.
