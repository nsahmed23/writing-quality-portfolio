Check what already owns port 8080 before touching Node itself:

1. `netstat -ano | findstr :8080` finds the process ID (PID) bound to the port.
2. `tasklist /FI "PID eq <PID>"` (use the PID from step 1) shows what that process is.

That's the useful move, because "Node 24 causes EADDRINUSE" isn't something I can confirm as a mechanism. Binding and releasing a TCP port happens in the Windows socket layer, not in Node's JS-level API, and that layer doesn't change with Node's version; I'm not aware of anything in Node 24 that touches it. What you've actually got is a sequence: you upgraded last Thursday, and the errors started around then. That's real, but it's a correlation, not a demonstrated cause, and I can't check your machine or repo to close that from here.

The detail that matters most is "every restart," not just the first launch of the day. That points at your own previous process, not a Node version change. Likely chain: nodemon kills the old process and starts a new one each time a watched file changes. Windows has no real POSIX signal support, so nodemon's usual graceful-restart signal (SIGUSR2 on POSIX systems) doesn't exist there, and its Windows fallback doesn't always reach the actual node.exe that ts-node spawned underneath it, only the wrapper process. The real listener survives, still bound to 8080, and the next restart's `server.listen(8080)` in server.ts fails against it. This is a known pattern with nodemon plus ts-node on Windows specifically, independent of Node version, since it's a process-tree and signal-handling problem, not a JS runtime one.

If the Node 24 upgrade also forced a fresh `npm install` that quietly bumped nodemon or ts-node to a newer version, that version bump is a more plausible trigger than Node 24 itself. I can't verify that without your package-lock.json from before and after; if it's committed, `git log -p -- package-lock.json` around last Thursday will show it.

One case points somewhere else entirely: if the very first `npm run dev` of the day also fails, before any restart happens, there's no leftover process yet, so it isn't this. That pattern usually means Windows has claimed 8080 itself, most often Hyper-V or WSL2 reserving it inside a dynamic port range after a Windows or Docker Desktop update. Check with `netsh interface ipv4 show excludedportrange protocol=tcp`.

Fixes, once you know which case you're in:

- Leftover node.exe holding the port: `taskkill /PID <PID> /F`, then stop it recurring with a real shutdown handler in server.ts (`process.on('SIGTERM', () => server.close())`, same for `SIGINT`), wherever it currently stores the return value of `.listen(8080)`.
- Still flaky after that: drop the nodemon-spawns-ts-node chain, since that's the part that loses track of children on Windows, in favor of `tsx watch src/server.ts`. One process, one watcher, nothing to orphan.
- Port excluded by Windows: pick a different port, or free the range; that's a Hyper-V/WSL2 fix, not a Node one.

Whichever process that PID turns out to be decides which fix applies.
