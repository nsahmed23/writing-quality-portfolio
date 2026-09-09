Node 24 isn't a documented cause of EADDRINUSE. I don't have its changelog in front of me to double-check, but nothing in Node's networking stack changed in a way that would affect how a port gets bound or released. I'd treat "since the upgrade" as a correlation worth investigating, not a confirmed cause, especially since EADDRINUSE on *every* restart is a well-known nodemon/Windows symptom that has nothing to do with which Node version is installed.

EADDRINUSE means: when the new process calls `.listen(8080)`, something else is still bound to that port. On a nodemon restart, that something else is almost always a process, not a Node internal.

Likely causes, most common first for nodemon + ts-node on Windows:

- **A leftover or duplicate process already on 8080.** An earlier `npm run dev` in another terminal or VS Code window that never actually exited, or a process left behind by switching Node versions (closing terminals for nvm-windows, a fresh MSI install, etc.), produces exactly this symptom on every subsequent restart.
- **nodemon or ts-node got bumped too.** If `npm install` ran again to sort out Node 24 compatibility, caret ranges in package.json may have pulled a newer nodemon/ts-node patch with different Windows behavior. Check with `npm ls nodemon ts-node`.
- **The nodemon-on-Windows restart race.** Windows doesn't support POSIX signals the way nodemon expects, so on Windows it kills the previous process tree with `taskkill` and immediately spawns the replacement, without waiting for confirmation the OS released the socket. This race predates Node 24; it's possible the new binary's startup timing just made an existing race more visible.
- **Windows reserved the port itself.** Docker Desktop, WSL2, and Hyper-V periodically claim dynamic port-exclusion ranges that can swallow 8080 with no process appearing to own it.
- **Defender scanning the new node.exe.** A freshly installed binary sometimes gets scanned on every launch until cached as trusted, which can slow shutdown right after an upgrade.

To find out which one it is:

1. `netstat -ano | findstr :8080`, then `tasklist /FI "PID eq <PID>"` for whatever PID owns it (PowerShell: `Get-NetTCPConnection -LocalPort 8080 | Select OwningProcess`).
2. If it's a stray node.exe: `taskkill /PID <PID> /F`, then run `npm run dev` clean.
3. If netstat shows nothing but the bind still fails: `netsh interface ipv4 show excludedportrange protocol=tcp` and check whether 8080 falls in a reserved range (fix is usually `net stop winnat` then `net start winnat`, as admin).
4. Confirm which Node nodemon is actually spawning: run `node -v` in the same shell you launch `npm run dev` from, in case a second install is still ahead of 24 on PATH.

If it's the restart race, the practical fix is nodemon's own throttle: pass `--delay 2000ms` in the `dev` script (or set nodemon.json's `delay` key) so there's a gap between kill and respawn. A `SIGINT` handler in `src/server.ts` that calls `server.close()` is good practice for clean Ctrl+C shutdowns, but won't fix the Windows kill-and-respawn race by itself.

I haven't seen `server.ts`, your `nodemon.json`/package.json, or actual netstat output, so I can't tell you which of the above is actually happening, just what to check. Paste back the netstat/tasklist output for port 8080 and I can narrow it down.