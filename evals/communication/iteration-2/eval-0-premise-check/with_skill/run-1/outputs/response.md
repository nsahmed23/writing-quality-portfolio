Run this first, in any Windows shell (cmd, PowerShell, or Git Bash all work):

```
netstat -ano | findstr :8080
```

Take the number in the last column, the PID, and check what owns it:

```
tasklist /FI "PID eq <PID>"
```

That tells you whether something is actually sitting on port 8080 right now, and what it is.

On "why does Node 24 cause EADDRINUSE": I can't confirm that premise, and I'd treat it as unverified rather than settled. You upgraded Node last Thursday, and the errors started around then; that's sequence, one thing happened before the other, not a demonstrated mechanism. EADDRINUSE itself is not a JavaScript-runtime behavior that changes with a Node version. It is the operating system refusing to let your process claim a port that something else already has bound, surfaced up through Node's `net` module. I don't know of a change in Node 24 to socket or port-binding defaults that would produce this, and I have no way to check the current changelog from here, so I am not ruling it out, only flagging that nothing connects the two yet.

The far more common explanation for EADDRINUSE on every restart with nodemon, especially on Windows, is that the previous process has not actually exited by the time nodemon starts the replacement. Windows has no native POSIX signals; nodemon emulates them and kills a process tree instead, which is less reliable there than on Linux or macOS, particularly when the child is a ts-node process rather than plain node. So the old listener on 8080 is still alive at the moment the new one tries to bind, every time. That is a process-lifecycle issue, not a runtime-version one, and it can start showing up after any environment change, a Node upgrade included, if that upgrade shifted how fast ts-node starts or exits.

1. If `tasklist` shows the PID as `node.exe` or a ts-node process, kill it (`taskkill /PID <PID> /F`) and run `npm run dev` again. A clean start means the bug is process cleanup, not Node 24.
2. Trigger a restart the normal way, by editing and saving a file, rather than restarting manually, and watch whether EADDRINUSE comes back. If it does on every single nodemon-triggered restart, nodemon is not fully killing the old ts-node process before relaunching, independent of which Node version is installed.
3. To test whether Node 24 is actually implicated, rather than just coincidental timing, run the same repo on Node 22 LTS for a few restarts. If it still breaks there, Node 24 is cleared and this is nodemon, ts-node, or Windows process handling. If it stops breaking, something in ts-node's or nodemon's Node 24 support is the real lead, and the next step is checking their installed versions against Node 24 compatibility notes.
4. If the first command shows nothing at all on port 8080, yet EADDRINUSE still fires, that rules out a lingering process. Check `netsh interface ipv4 show excludedportrange protocol=tcp` for 8080 falling inside a range Hyper-V, WSL2, or Docker Desktop has reserved; that produces the same error with no process to find.

I have not seen `server.ts`, your `nodemon.json`, or an actual process listing, so I cannot tell you which of these it is, only which is most likely given every restart, plus Windows, plus nodemon, plus ts-node. The `tasklist` output from the first command decides which branch above applies.
