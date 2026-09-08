EMFILE isn't something *caused by* running out of file descriptors (a file descriptor is the small integer the kernel hands your process for every open file, socket, or pipe); it *is* the kernel's refusal, in real time, when your Node process tries to open one more than its configured limit allows. Same event, described two ways, not two events in a chain.

That distinction matters because two different limits get confused under similar error names:

- **EMFILE**: your process hit its own cap, `RLIMIT_NOFILE` (the per-process ceiling on open descriptors, what `ulimit -n` reports in a shell). This is what your error is.
- **ENFILE**: the whole system hit `fs.file-max`, a kernel-wide tunable, not a per-process one. Different error text, different fix, not what you're seeing.

So the real question is why your Fastify process's own descriptor count climbs until it hits that per-process ceiling. Two mechanisms fit "dies after ~6 hours under load," and they point to different fixes. If the ceiling is simply too low for real concurrent load, crashes should track traffic spikes, and the open-fd count should plateau near the limit rather than creep upward while traffic stays flat. If something is opening descriptors faster than it closes them, the count climbs steadily whether traffic is flat or rising, and hits the ceiling on a schedule set by the leak rate, not by peak concurrency. If the ~6-hour timing has repeated across more than one crash and stayed roughly the same even when traffic varied, that favors the leak. Step 3 below settles it either way.

**Check this first** (works the same whether you run via systemd, pm2, Docker, or bare `node`; prefix commands with `sudo` if the process runs as a different user than you):

1. Find the PID: `pgrep -af node` (10 seconds).
2. Read the limit actually applied to that running process, not what a different shell's `ulimit -n` reports: `cat /proc/<pid>/limits`, the "Max open files" row. Ubuntu 22.04's systemd default (`DefaultLimitNOFILE`) is typically soft 1024 / hard 524288 unless a unit sets `LimitNOFILE=` explicitly, but read the actual number rather than assuming it.
3. Watch it over time under normal load: `watch -n 30 'ls -1 /proc/<pid>/fd | wc -l'`. A steady climb with flat traffic means a leak; a plateau that only shows up at peak traffic means undersized capacity.
4. Break down what's open: `ls -l /proc/<pid>/fd | awk '{print $NF}' | sort | uniq -c | sort -rn | head -20` for file-type descriptors, and `ss -tnp state close-wait | grep <pid>` for sockets stuck in `CLOSE_WAIT` (the remote end closed the connection, but your process never closed its side).
5. If it runs under systemd, confirm nothing already overrides the limit: `systemctl show <service> -p LimitNOFILE`.

**If step 3 shows a climb, the usual causes in a Fastify app behind nginx, roughly by frequency:**

1. Outbound calls (to another API, a database, Redis) whose sockets end up in `CLOSE_WAIT` because the remote closed and your code never called `.destroy()` or `.end()` on its own end; the `ss` command above shows this directly.
2. An HTTP client agent with no `keepAlive`/`maxSockets` cap, opening a new socket per outbound call instead of reusing a pool.
3. `fs` streams (`createReadStream`/`createWriteStream`, or plugins like `@fastify/multipart` and `@fastify/static`) that error before `'close'` fires, where the handler doesn't catch the error and explicitly destroy the stream.
4. A database, Redis, or queue connection pool where a thrown error skips the code path that releases the connection back to the pool.
5. Long-lived WebSocket or SSE connections whose cleanup handler doesn't run on an abrupt client disconnect.

If it's the first branch (undersized ceiling), raising `LimitNOFILE` to match real peak concurrency is a genuine fix. If it's the second (a leak), raising the limit only buys more hours before the same crash; the code path that isn't closing descriptors has to be fixed instead.

One thing this rules out: nginx isn't the process hitting the limit here. The text you pasted, `Error: EMFILE: too many open files`, is Node's own libuv-formatted error; nginx would log a distinct message to its own error log if it hit its separate `worker_rlimit_nofile`. Whichever branch this turns out to be, the fix is on the Node side, not the nginx config.

What I haven't verified, because I don't have your server or code: how the process is actually launched (systemd unit, pm2, Docker, plain `node`), its real current limit, your nginx upstream keepalive settings, and what outbound calls or streams your route handlers make. Steps 1 through 5 above will settle all of that from your side.

Next: run `pgrep -af node` and `cat /proc/<pid>/limits` now, before the next crash, so you have the real soft limit on record.
