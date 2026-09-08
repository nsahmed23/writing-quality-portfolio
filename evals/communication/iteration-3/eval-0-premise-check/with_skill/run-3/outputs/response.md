1. Run `netstat -ano | findstr :8080` (the last column is the PID of whatever already has port 8080; that's what EADDRINUSE means, the address is already taken).
2. Look up that PID: `tasklist /fi "PID eq <pid>"`, swapping in the number from step 1.
3. If it's a leftover `node.exe`: `taskkill /PID <pid> /F`, then run `npm run dev` again.

Under two minutes, and it settles the real question.

Whether Node 24 is actually the cause is unverified. I don't know of a networking change in Node 24 that would make `.listen()` throw EADDRINUSE where earlier versions didn't, and I have no way to check the changelog from here. What you're describing (EADDRINUSE on every restart, starting right after an upgrade) is the standard symptom of a leftover process still holding the port, and that fits nodemon on Windows specifically. Windows has no real POSIX signals (the OS-level "stop this process" messages nodemon relies on for a clean restart on Mac and Linux), so nodemon's kill-and-respawn cycle, which spawns `ts-node src/server.ts` as a child process and then signals it to restart, doesn't always fully kill that child. A `node.exe` from a previous run can keep running in the background, invisible, still bound to 8080; every `npm run dev` after that collides with it.

The Thursday timing is most likely coincidence, not cause. Switching Node versions usually means closing and reopening a terminal or VS Code, and that's exactly the kind of moment a nodemon-spawned child gets orphaned instead of cleanly killed. One orphan on 8080 stays there through every later restart, which looks identical to "started when I upgraded" without Node 24 having done anything.

Two things I can't verify without your files: whether `src/server.ts` calls `.listen()` more than once (a second, unrelated way to get this exact error), and whether another terminal or VS Code tab is still running last week's `npm run dev`. The netstat output above rules both in or out.

If this keeps recurring after you kill the orphan, the durable fix is dropping nodemon and ts-node for `tsx watch src/server.ts`: tsx tears down its watched process more reliably on Windows and skips the separate ts-node compile step.

Next: run the netstat command and tell me the PID (or "nothing") on port 8080.