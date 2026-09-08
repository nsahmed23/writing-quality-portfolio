EMFILE isn't a separate effect that running out of file descriptors causes; it *is* that event. The moment your process tries to open a new socket or file and the kernel refuses because you're already at your file-descriptor ceiling, that refusal is what comes back as `EMFILE: too many open files`. So the question underneath yours, and the one actually worth chasing, is why your process's open-descriptor count keeps climbing for six hours until it hits that ceiling.

A few things worth pinning down first:

- The error format you pasted (`Error: EMFILE: ...`) is Node/libuv's, not nginx's. This is failing inside your Fastify process, not in nginx. Nginx has its own separate cap (`worker_connections`), but it isn't what's throwing here.
- The full line in your logs ends with the syscall that failed, for example `..., accept` (couldn't accept a new inbound connection) or `..., open '/some/path'` (couldn't open a file). That tells you sockets versus file handles. Worth pulling the untruncated line if you still have it.
- EMFILE is a per-process limit. `ENFILE` is the separate, much rarer system-wide table exhaustion. A single process crashing repeatedly, rather than everything on the box failing at once, points at the per-process ceiling (`ulimit -n`), not the system-wide one.
- An EMFILE that surfaces unhandled on the server's accept loop crashes the whole process (Node's default when an error goes unhandled is to exit), which is why you get a hard death instead of a handful of failed requests. If your systemd unit has `Restart=on-failure`, that also explains why it's a repeating ~6-hour cycle rather than one outage.

## Why it takes six hours

Every open socket or file counts against the ceiling: inbound connections from nginx, outbound connections to a database, cache, or external API, and any files you open. A slow crawl toward the limit over hours means one of two things. Either something leaks a few descriptors per request that never get closed, or your legitimately concurrent connection count is growing (long-lived connections piling up faster than they close) past a ceiling that was never sized for real peak load. Both produce the same symptom and the same error. The check below tells them apart.

## Find out which, before fixing anything

I can't see your code or how the process is deployed, so I can't tell you which call is responsible, but this is checkable directly on the box:

1. Get the PID: `systemctl status <your-service>` or `ps aux | grep node`.
2. Check the limit actually enforced on that process, not your shell's: `cat /proc/<pid>/limits | grep "open files"`. This can differ from what `ulimit -n` shows you in a terminal.
3. Watch the count over time: `watch -n 5 'ls /proc/<pid>/fd | wc -l'`, left running while real traffic hits the app. Flat means fine; climbing confirms the ceiling is actually being approached, not just eventually hit.
4. See what's accumulating: `ls -l /proc/<pid>/fd`, or `lsof -p <pid>` if you have it (`sudo apt install lsof`). Sockets versus regular files tells you which half of the code to look at.
5. If it's sockets, check their state: `ss -tnp | grep <pid>`. A growing pile of `CLOSE_WAIT` means the remote end closed and your code never called `.destroy()`/`.end()` on its side; that is a leak. A growing pile of `ESTABLISHED` that roughly tracks your real concurrent client count means there's no bug; you just have more legitimate open connections than the ceiling allows. (`TIME_WAIT` doesn't count against your process's descriptors either way, ignore it.)

## If it's CLOSE_WAIT: likely spots, ranked

1. Outbound HTTP calls (`fetch`/undici, axios, `http.request`) opening a new connection or agent per request instead of reusing one shared keep-alive agent.
2. Database or Redis pool clients acquired but not released on error paths: a missing `finally` around `client.release()` or its equivalent.
3. File streams (`fs.createReadStream`/`createWriteStream`, multipart upload handling) left open when a request errors or the client disconnects mid-upload.
4. WebSocket or SSE connections whose disconnect handler doesn't tear down what it opened.
5. A custom logger or log file stream reopened per request instead of once at startup.

## Raising the limit: fix or stopgap

Which one it is depends on step 5 above. If you saw legitimate `ESTABLISHED` connections outgrowing the ceiling, raising it is the actual fix (check that nginx's `worker_connections` and the system-wide `fs.file-max` have headroom too, so you're not just moving the wall). If you saw `CLOSE_WAIT` piling up, raising it only delays the identical crash; the real fix is closing whatever step 5's ranked list points at.

Either way, on Ubuntu with systemd: editing `/etc/security/limits.conf` alone will not touch a systemd-managed service, since that file is read by PAM at login and systemd doesn't start services through a login session. Set it in the unit instead: `LimitNOFILE=65536` under `[Service]`, then `sudo systemctl daemon-reload && sudo systemctl restart <your-service>`. Running under pm2 or Docker instead, the equivalent is the ulimit of whatever process starts pm2, or `--ulimit nofile=65536:65536` on the container.

Next: get the PID and run steps 2 and 3 right after a restart, then again an hour into load. The growth rate, or lack of one, tells you which branch you're actually in.
