Run `netstat -ano | findstr :8080`. The number in the last column of the matching line is the PID currently holding port 8080.

Before treating "Node 24 causes this" as settled: what you actually have is that the errors started after the upgrade, and that is sequence, not a demonstrated cause. I don't know of a change in Node 24 to how sockets bind to a port, and I don't have web access in this task to check the v24 changelog line by line, so treat that absence as unconfirmed rather than ruled out. What doesn't change across Node versions is what EADDRINUSE actually is: the operating system telling a process that something is already bound to a port when it tries to listen on it. That's an OS-level condition, not a Node language feature.

The more likely explanation doesn't need Node 24 at all. On Windows with nodemon plus ts-node, the common cause is a process still holding 8080 from before you touched anything. One version: an old terminal from before the upgrade still has `npm run dev` running under the previous Node install, quietly holding the port while you test in a new terminal. Another version: nodemon killed the previous ts-node process on a restart, but Windows has no native SIGTERM, so nodemon simulates the kill, and that simulation occasionally hasn't finished freeing the socket before the new process tries to bind it. That would explain why it happens on every restart rather than once.

With the PID from netstat:

1. Identify it: `tasklist /FI "PID eq <that PID>"`.
2. If it's `node.exe`: `taskkill /PID <that PID> /F`, then run `npm run dev` again.
3. If it's anything else, a different program has claimed 8080, not Node; stop that program or change the port `server.ts` listens on.

If netstat returns nothing at all for `:8080`, no process holds it, and the cause shifts to a Windows-level reservation instead of a leftover process. Check `netsh interface ipv4 show excludedportrange protocol=tcp` and see whether 8080 falls inside a listed range.

What I can't check from here: I don't have access to `C:\Dev\Projects\inventory-api\src\server.ts`, so I can't confirm `.listen()` is only called once, whether there's SIGINT or SIGTERM handling to close the server on shutdown, or what your `nodemon.json` does on restart. I also can't tell whether the Node 24 upgrade quietly pulled in a new nodemon or ts-node version through your lockfile; `npm ls nodemon ts-node` shows the installed versions against whatever you had before.

Next: to get real evidence on whether Node 24 is involved at all, switch back to your previous Node version in the same repo and run `npm run dev` once. If EADDRINUSE still happens, that clears Node 24 outright and confirms the leftover-process explanation.
