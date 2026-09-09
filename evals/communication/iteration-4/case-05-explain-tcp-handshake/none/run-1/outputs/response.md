TCP's handshake is really two handshakes, one per direction, overlapped so they cost three packets instead of four.

## The counting argument

TCP is full duplex, and each direction is an independent byte stream with its own sequence number space. Each side picks its own Initial Sequence Number (ISN) for the stream it will send. Before either side can send data safely, four things have to be true:

1. Client announces its ISN, `x`.
2. Server acknowledges `x`.
3. Server announces its ISN, `y`.
4. Client acknowledges `y`.

Facts 2 and 3 both travel server to client, so they ride in a single segment with the SYN and ACK flags set together. Four required facts, three packets. A two-packet exchange gives you facts 1 through 3 and silently drops fact 4: the server announces its ISN and then just assumes the client heard it.

You can see the underlying four-message structure whenever the piggybacking is impossible. In a simultaneous open (both sides send SYN at once, which shows up in some peer-to-peer NAT traversal), you get four segments: SYN, SYN, SYN-ACK, SYN-ACK.

## What actually breaks with two

The failure mode is not theoretical; it is the reason the spec is written this way (RFC 793, now RFC 9293).

Suppose a client sends a SYN and the segment gets stuck somewhere: a routing loop, or a link that buffers and then flushes. The client times out, retries on a fresh connection, finishes its business, and goes away. Minutes later the stranded SYN finally arrives at the server.

With a two-way handshake the server has no further questions to ask. It replies SYN-ACK, marks the connection ESTABLISHED, allocates buffers, and hands the socket to the application. If any of that old connection's data segments are also still wandering around, they now land in a live connection with plausible sequence numbers and get delivered as real data. The server is talking to a ghost.

With three, the server sends SYN-ACK and waits. The client receives an acknowledgment for a connection it never opened, replies RST, and the server tears the half-open connection down before the application ever sees it. The third packet is what gives the client a veto.

## What else that third packet buys

**A validated send space.** Once the ACK arrives, the server knows a real peer received `y` and is ready to receive data starting at `y+1`. Without it the server is transmitting into the dark.

**Return routability.** Completing the handshake requires actually receiving the server's SYN-ACK, which means being reachable at the claimed source address. An off-path attacker spoofing a source IP never sees the SYN-ACK and would have to guess the server's ISN, which is why ISNs are generated from a keyed hash rather than a simple counter (RFC 6528). It is also why SYN floods work: they exploit the one window where the server has committed state but has not yet validated the peer. SYN cookies close that window by encoding the server's state into `y` itself, so no memory is allocated until the final ACK comes back.

## Why three, and why not chase four or five

Worth noticing: three does not actually give both sides certainty. After the SYN-ACK the client knows both ISNs are agreed. After the final ACK the server knows too, but the client does not know that the server knows, and no finite number of messages fixes that (the Two Generals problem). Three is not the number that produces mutual certainty. It is the minimum that bootstraps both sequence spaces, and TCP absorbs the leftover uncertainty the way it absorbs everything else, with retransmission timers.

For contrast, teardown is four-way (FIN, ACK, FIN, ACK) and does not collapse, because a half-close is meaningful. One side can stop sending while still receiving, so the middle two messages carry genuinely independent decisions and cannot be merged into one.

## The modern exceptions

The price of all this is one round trip before the first byte of application data. Two ways around it:

- **TCP Fast Open** (RFC 7413) lets the client put data in the SYN itself, using a cryptographic cookie issued during an earlier ordinary connection. The cookie substitutes for the round-trip proof of address ownership. It is essentially the two-way handshake you are asking about, made safe by moving the validation offline.
- **QUIC** folds the transport handshake into the TLS 1.3 handshake, so a new connection reaches encrypted data in one RTT and a resumed one can do it in zero.

Both confirm the framing. Three packets is not a magic number; it is the cheapest way to establish and validate two sequence spaces when you have no prior state with the peer. Give the two parties prior state and the count drops.
