Short version: this almost certainly isn't Node 24. EADDRINUSE means something already has port 8080 bound when your server tries to bind it; that's an OS-level condition, not a runtime feature that a Node version bump changes. I'm not aware of any Node 24 change to socket-binding defaults, and I can't check the changelog from here, so the claim that Node 24 causes this stays unconfirmed rather than settled.

The real tell is that this happens on every restart, not on first start. That's the signature of nodemon not fully killing the previous ts-node child before spawning the new one. Windows doesn't support POSIX signals the way nodemon expects, so its restart signal (SIGUSR2, falling back to SIGTERM) often fails to tear down the old child cleanly. The old process stays alive holding 8080, the new one tries to bind on top of it, and you get EADDRINUSE. This is a known nodemon-on-Windows issue that has nothing to do with which Node version you're running.

The timing next to your upgrade is more likely coincidence than cause:

1. A `npm run dev` instance from before the upgrade may still be running in another terminal or VS Code tab, quietly holding 8080.
2. Moving to Node 24 usually means reinstalling `node_modules`, which can pull newer `nodemon`/`ts-node` versions with different Windows child-process handling than what you had before.

To find out what's actually holding the port:

1. `netstat -ano | findstr :8080` (PowerShell: `Get-NetTCPConnection -LocalPort 8080`) to get the PID bound to it.
2. `tasklist /FI "PID eq <pid>"` (PowerShell: `Get-Process -Id <pid>`) to see what that PID is. A `node.exe` that isn't your current terminal's process is your leftover instance.
3. `taskkill /PID <pid> /F` (PowerShell: `Stop-Process -Id <pid> -Force`), then run `npm run dev` again.

If netstat shows nothing bound to 8080 at all, the cause is different: check `netsh interface ipv4 show excludedportrange protocol=tcp` for Windows-reserved port ranges. Hyper-V, WSL2, and Docker Desktop all reserve blocks of ports, and one of those getting installed or updated around the same time as Node could have swallowed 8080.

For a fix that doesn't mean hunting a PID every time: set `"signal": "SIGKILL"` in `nodemon.json` so restarts hard-kill the child instead of relying on a graceful signal Windows won't deliver properly, and update nodemon to the latest 3.x, since Windows child-process handling has improved there. A blunter option is `npx kill-port 8080 && nodemon ...` in the dev script, which clears the port before every restart regardless of what's holding it.

What I can't verify: I don't have access to `inventory-api`, so I haven't seen `server.ts`, `nodemon.json`, or your installed nodemon/ts-node versions, and I have no way to confirm or rule out a Node 24 changelog entry from here. Run the `netstat` command first; the PID it returns will tell you definitively whether this is a leftover process or something else.