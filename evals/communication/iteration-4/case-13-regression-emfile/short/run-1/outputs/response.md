Running out of file descriptors does not *cause* `EMFILE`; it *is* `EMFILE`. When your process asks the kernel for a new descriptor (a small integer handle the kernel hands back for an open file, socket, pipe, epoll instance, or inotify watch) and the process already holds as many as its `RLIMIT_NOFILE` soft limit allows, the syscall fails with errno 24, and libuv surfaces that to JavaScript as `Error: EMFILE: too many open files`. There is no intermediate mechanism to explain between the two.

The question worth answering is why your descriptor count climbs for six hours instead of leveling off, and that one has a measurable answer.

## The six-hour ramp is most of the diagnosis

Two different faults produce this error, and they behave differently.

A limit that is simply too low for your legitimate concurrency fails *at peak*. It tracks traffic, hits the wall at a reproducible request rate, and clears when load drops. Uptime is irrelevant to it.

A descriptor leak fails *on a clock*. The count rises monotonically, never falls during quiet periods, and time-to-death scales inversely with request rate. Six hours of steady load and then death is the leak signature. The confirming test: double the load, and if it dies in roughly three hours it is a leak; if it dies at the same absolute traffic level no matter how long it has been up, it is the limit.

Measure that before changing anything. Everything below assumes a leak, which is the likelier reading of what you described, but I cannot see your server and have not confirmed it.

## Localize it, in this order

1. **Find the limit the service actually runs under.**

```
systemctl show <your-service> -p LimitNOFILE -p LimitNOFILESoft
cat /proc/$(pgrep -f 'node.*yourapp')/limits | grep 'open files'
```

`ulimit -n` in your shell is not what systemd gives the service. And `/etc/security/limits.conf` does not apply to systemd units at all (PAM applies it at login), which is the most common reason a "raised" limit has no effect. On Ubuntu 22.04 the service default is typically 1024 soft / 524288 hard, but read it rather than assume it. If you run under Docker or PM2, the numbers come from there instead.

2. **Plot the count over time.** Do not spot-check it.

```
PID=$(pgrep -f 'node.*yourapp')
while true; do echo "$(date +%s) $(ls /proc/$PID/fd | wc -l)"; sleep 30; done >> /tmp/fdcount.log
```

A straight upward line confirms the leak and gives you its slope in descriptors per request.

3. **Break the descriptors down by type.** This is the step that names the bug.

```
sudo lsof -p $PID | awk '{print $5}' | sort | uniq -c | sort -rn
```

Column 5 is TYPE. Growth in `IPv4`/`IPv6` means sockets, `REG` means regular files, `FIFO` means pipes, and `a_inode`/`unknown` is usually eventpoll or inotify.

4. **If it is sockets, get the states and the peers.**

```
sudo ss -tanp | grep "pid=$PID" | awk '{print $1}' | sort | uniq -c
sudo ss -tanp | grep "pid=$PID" | awk '{print $5}' | sort | uniq -c | sort -rn | head
```

`CLOSE_WAIT` piling up means the peer closed and your process never closed its end, which is nearly always an HTTP response body that was never consumed or destroyed. A growing wall of `ESTABLISHED` toward one upstream address means an outbound client is being constructed per request instead of reused. Rule out `TIME_WAIT` explicitly: those sockets are held by the kernel, not by your process, and do not consume your descriptors (they consume ephemeral ports, which is a different exhaustion with a different error).

5. **Recover the full error line from your logs.** Node's message normally carries the failing syscall and path, for example `EMFILE: too many open files, open '/var/app/uploads/x.tmp'` or `..., connect`. You quoted it without that suffix, so either it was trimmed in the paste or something is re-wrapping the error. That suffix names the leaking subsystem directly. Related and useful: libuv keeps a spare descriptor in reserve precisely so `accept()` degrades gracefully under EMFILE rather than throwing, so an EMFILE that reaches application code usually came from `open`, `connect`, or `spawn`, not from accepting inbound connections. That points away from nginx and toward what your handlers do.

6. **Optional, and worth it.** On Linux, `fs.readdirSync('/proc/self/fd').length` is cheap enough to emit every 30 seconds alongside your other metrics. Then the next occurrence is read off a dashboard instead of reconstructed after the fact.

## Candidates, given the shape

Ranked by how often they produce exactly this profile. These are mechanisms to check, not findings about your code:

- **Outbound HTTP responses never drained.** With `undici`, `fetch`, `axios`, or `node-fetch`, a response whose body you never read keeps its socket open. Error and early-return paths are where this hides: you inspect `res.statusCode`, throw, and never touch `res.body`. Fix is `res.body.dump()` on undici, `res.resume()` on core `http`.
- **Per-request clients.** A `new undici.Pool(...)`, `new Agent(...)`, `new pg.Client(...)`, or `new Redis(...)` inside a route handler rather than at module scope. Each instance owns its own sockets and nothing collects them.
- **Streams without abort handling.** `fs.createReadStream` piped to a reply where the client disconnects mid-transfer. Fastify will not destroy it for you.
- **Multipart uploads.** `@fastify/multipart` temp files unlinked only on the success path.
- **Watchers or config reloaders** re-registering without closing the previous handle.

Your nginx keep-alive connections are legitimate and bounded (upstream `keepalive N` times worker count), so they raise the floor but should plateau rather than climb. They are not the leak.

## Raising the limit

Do it, but as a shock absorber that buys diagnosis time, not as a fix. A leak at any slope eventually reaches any ceiling.

```
sudo systemctl edit <your-service>
```

Add:

```
[Service]
LimitNOFILE=65535
```

Then:

```
sudo systemctl daemon-reload
sudo systemctl restart <your-service>
cat /proc/$(pgrep -f 'node.*yourapp')/limits | grep 'open files'
```

Verify with that last command rather than trusting the edit. If the number did not change, you edited the wrong unit or something other than systemd is supervising the process.

## What I could not verify

I have no access to your server, code, logs, or traffic. The premise correction and the mechanism (EMFILE is the report of exhaustion, not a consequence of it) are certain. The leak-versus-limit split is well established, but which one you have is unconfirmed until the curve from step 2 exists. The candidate list is mechanisms, not a diagnosis of your app.

Post the type breakdown from step 3, the state histogram from step 4, and the full error line with its syscall suffix, and that is normally enough to name the specific bug.
