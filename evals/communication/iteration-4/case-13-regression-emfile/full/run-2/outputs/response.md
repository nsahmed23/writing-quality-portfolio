Yes, that is the cause, and the chain is short. Every open file, socket, and pipe a process holds is tracked by a file descriptor (a small integer the kernel hands back from `open`, `accept`, or `socket`). The kernel caps how many one process may hold at once, a limit called `RLIMIT_NOFILE`. Once the process sits at that cap, the next syscall that needs a fresh descriptor does not queue or wait; it fails immediately with errno 24, EMFILE. libuv, the C library Node uses for I/O, passes that errno up and Node surfaces it as `Error: EMFILE: too many open files`. In a Fastify app the failing call is usually `accept()` taking a new inbound connection, `open()` on a file read, or `socket()` opening an outbound HTTP or database connection.

That also explains why it dies instead of just serving errors: an EMFILE from `accept()` arrives as an `'error'` event on the HTTP server, and an `'error'` event with no listener becomes an uncaught exception, which exits the process.

Worth holding onto: EMFILE is the per-process ceiling, ENFILE is the system-wide file table. You are getting EMFILE, so this is your Node process's own budget. nginx's `worker_rlimit_nofile` is a separate budget and is not implicated by this error string.

The mechanism above is settled. Why your count climbs for six hours instead of leveling off is not, and I cannot see your server, so the steps below are how to find that out, not a diagnosis. Under steady load with correct cleanup the descriptor count plateaus. A slow climb means either descriptors are opened and never closed, or the ceiling is simply too low for your real concurrency and ordinary drift takes six hours to reach it. Those two look identical until you measure. Run all of this as root or as the service's user, since `/proc/<pid>/fd` is readable only by its owner.

1. Get the real ceiling for the running process. `ulimit -n` in an SSH session reports your login shell's limit, which routinely differs from the service's.

   ```
   pid=$(systemctl show -p MainPID --value your-service)
   grep 'open files' /proc/$pid/limits
   ```

   A systemd-managed service on 22.04 typically inherits a soft limit around 1024 with a much larger hard limit, but read yours rather than assuming it.

2. Watch the count climb so you know the shape of the growth. About 30 seconds to start, then leave it running for an hour under normal load.

   ```
   while sleep 60; do echo "$(date +%T) $(ls /proc/$pid/fd | wc -l)"; done
   ```

   A straight line means a leak proportional to traffic. A step increase at a fixed time of day points at a cron job or a scheduled batch instead.

3. Find out what the extra descriptors actually are. This is the step that names the bug.

   ```
   lsof -p $pid | awk '{print $5}' | sort | uniq -c | sort -rn
   ```

   `REG` growing means file streams never closed, usually on an error or client-abort path that skips the close. `IPv4` or `IPv6` growing means sockets. If lsof is not installed: `ls -l /proc/$pid/fd | awk '{print $NF}' | cut -d'[' -f1 | sort | uniq -c | sort -rn`.

4. If it is sockets, split them by TCP state, because the state names the owner.

   ```
   ss -tanp | grep "pid=$pid," | awk '{print $1}' | sort | uniq -c
   ```

   A pile of `CLOSE_WAIT` means the far end closed and your code never called close on its side, which is your app leaking. A pile of `ESTABLISHED` all pointing at one downstream address means an outbound client opening a fresh connection per request instead of reusing a pooled agent.

5. Raise the limit last, not first. `systemctl edit your-service`, add `[Service]` and `LimitNOFILE=65535`, then `systemctl daemon-reload && systemctl restart your-service`. This doubles as the deciding test: if the count plateaus well below 65535, you were undersized and you are done. If it climbs to the new ceiling and dies at eighteen hours instead of six, it is a leak and step 3 tells you where it lives.

Next: run the `grep 'open files' /proc/$pid/limits` line and the lsof count once, back to back. Those two numbers, the ceiling and what is filling it, decide everything else.
