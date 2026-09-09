Run `netstat -ano | findstr :8080` to see what's currently bound to the port, then match the PID it returns against `tasklist /FI "PID eq <pid>"` to identify the process. Two minutes to check, and the fix depends on what you find.

Node 24 causing this isn't confirmed. Upgrading last Thursday and the errors starting afterward is a timing match, not evidence of a mechanism, and I don't have access to your machine or logs to check further. Your own description actually argues against a Node-24-wide problem: it fails on every restart, not on first launch. If Node 24 itself couldn't bind a listening socket, the first `npm run dev` after a clean boot would fail too, not just the restarts.

Failing on restart but not on first start points somewhere much more mundane: nodemon starting the replacement server before Windows finishes releasing port 8080 from the process nodemon just killed. On Windows, nodemon tears down the old process by running the `taskkill` command as a separate, asynchronous step, and it doesn't necessarily wait for Windows to confirm the socket is fully closed before launching the new one. That's a Windows/nodemon timing issue, not a Node 24 one, though an unrelated Node upgrade can still be what exposed it: if compiling under Node 24 runs at a different speed, it shifts the timing of the race.

To confirm and fix:

1. Read the PID from the netstat/tasklist check above right after the next EADDRINUSE. A leftover `node.exe` supports the restart-timing theory; if confirmed, `taskkill /PID <pid> /F` clears it immediately. Anything else means a different, unrelated process owns 8080.
2. Rule out a cold-start failure: close every terminal running the dev server, confirm `netstat -ano | findstr :8080` comes back empty, then run `npm run dev` once. If it still throws EADDRINUSE with nothing visibly on the port, run `netsh interface ipv4 show excludedportrange protocol=tcp` and check whether 8080 sits in a reserved range (a common side effect of Hyper-V or WSL2 on Windows, and unrelated to Node).
3. Check whether nodemon or ts-node moved versions alongside Node, since that's just as plausible a cause as Node itself: run `npm ls nodemon ts-node typescript`.
4. If step 1 points to a leftover `node.exe`, add a restart delay so nodemon waits for Windows to finish tearing down the old process before relaunching. Add a `delay` setting to `nodemon.json` (or the `nodemon` key in `package.json`), and check `nodemon --version` against nodemon's docs for whether your installed version expects the value in seconds or milliseconds; something equivalent to one to two seconds is usually enough.

If the delay doesn't fully fix it, the more durable fix is a graceful shutdown handler in `server.ts`: `process.on('SIGTERM', () => server.close())`, so the HTTP listener closes explicitly instead of waiting on the OS to reclaim the socket after the process dies.

Next: reproduce the error once, and read the process name behind the PID that step 1 turns up.
