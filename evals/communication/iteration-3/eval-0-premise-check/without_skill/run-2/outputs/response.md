Node 24 isn't a documented cause of EADDRINUSE. Nothing in its release notes touches port binding or process exit. The error itself is an OS-level check (something is already bound to port 8080) that a runtime version doesn't control.

The upgrade timing is most likely coincidental rather than causal. Something else probably changed alongside it: reinstalled `node_modules`, a different nodemon or ts-node version pulled in during install, or a stale process left running from before you upgraded. One of those is squatting on the port, not Node 24 itself.

The pattern you're describing (works on a cold start, fails on every nodemon restart) is the classic signature of the previous process not fully releasing port 8080 before the new one tries to bind it. This is a known rough edge on Windows specifically: Windows has no native SIGTERM, so nodemon has to emulate the kill, and since `ts-node` runs as a spawned child process under nodemon, the parent can be torn down while the child (still holding the socket) lingers.

Three things to check, in order:

1. **Confirm what's actually on port 8080.** In PowerShell:
   ```powershell
   Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Select-Object LocalPort,State,OwningProcess
   Get-Process -Id <PID from above>
   ```
   If that PID is a leftover `node.exe`, that confirms an orphaned-process problem, not a Node-version problem. Run `Stop-Process -Id <PID> -Force`, then restart once to verify the theory.

2. **Check for a graceful shutdown handler in `server.ts`.** If it's just `app.listen(8080)` with nothing closing the server on exit, nodemon's restart can race the old process's teardown against the new process's bind:
   ```ts
   const server = app.listen(8080, () => console.log('listening on 8080'));
   process.on('SIGTERM', () => server.close(() => process.exit(0)));
   process.on('SIGINT', () => server.close(() => process.exit(0)));
   ```

3. **If `Get-NetTCPConnection` shows nothing on 8080 and you still get EADDRINUSE**, that points to a different Windows issue: Hyper-V, WSL2, and Docker Desktop all periodically reserve TCP port ranges, which can knock out a previously free port after an update or reboot with no Node involvement at all.
   ```powershell
   netsh interface ipv4 show excludedportrange protocol=tcp
   ```

One more angle worth a quick check, since you're on `ts-node`: its maintenance has slowed and it isn't guaranteed to be validated against brand-new Node majors. If you're on an older `ts-node` version, it's worth confirming compatibility with Node 24 specifically, rather than assuming Node itself is at fault.

I haven't seen `server.ts`, your `nodemon.json`, the `package.json` dev script, or the actual PID and error output, so I can't tell you which of these three it is, only that "Node 24 causes it" isn't the right framing. Step 1's output will point you at the real answer.
