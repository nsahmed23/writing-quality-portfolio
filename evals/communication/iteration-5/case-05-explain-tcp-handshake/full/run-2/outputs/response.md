Because two starting points have to be agreed on, not one, and each side has to hear that its own starting point arrived. That is four pieces of information, and two of them can travel in the same packet, which leaves three.

### The four facts, three packets

TCP numbers every byte it sends so the receiver can reassemble them in order and notice gaps. Each direction of a connection has its own counter, and each side picks its own starting value rather than beginning at zero (the initial sequence number, or ISN; it is chosen unpredictably so that an off-path attacker cannot forge segments into the stream, and so that stray packets from an earlier connection between the same two ports do not look valid). Opening a connection therefore means settling four things:

1. A's ISN, told to B
2. B's confirmation that it received A's ISN
3. B's ISN, told to A
4. A's confirmation that it received B's ISN

Items 2 and 3 are both things B says to A at the same moment, so B puts them in one segment. Item 4 cannot be merged with anything, because A cannot confirm B's ISN before it has seen it. That gives:

```
A -> B   SYN,     seq=x            "I am starting at x"   (SYN = synchronize, the open-a-connection flag)
B -> A   SYN+ACK, seq=y, ack=x+1   "I am starting at y, and I have yours"
A -> B   ACK,     ack=y+1          "I have yours"
```

Written out, the asymmetry is the whole story: A knows everything it needs after the second packet. The third packet exists for B's benefit.

### What breaks if you stop at two

Under a two-packet handshake, B would treat the connection as open the moment it sent its reply, having heard nothing back. Two things then go wrong.

**The SYN+ACK is lost.** B has already declared the connection open and handed it to the application, which starts writing data. A never learned the connection exists and does not have B's ISN, so it cannot order or acknowledge anything B sends; it discards what arrives and keeps retransmitting its own SYN. The two ends sit in disagreement until one of them times out. The third packet turns this into an ordinary retransmission instead: no ACK arriving means the SYN+ACK did not get there, so B resends the SYN+ACK rather than pushing data into a connection that exists on only one side.

**An old SYN shows up late.** A abandons a connection attempt, but one of its SYNs is still in the network on a slow path and reaches B minutes later. With two packets, B replies and opens a connection nobody wants, committing buffers and accepting data numbered from an attempt that is already over. With three, A receives a SYN+ACK for a connection it is not opening and answers RST (reset, meaning "no such connection here"), and B tears the half-open connection down. The third packet is the initiator's chance to disown a stale request, and this is the case the original TCP specification (RFC 793, now replaced by RFC 9293) gives as the reason for it.

### The third packet costs almost nothing

Three packets still mean one round trip before A can send data, exactly as two would, because A's ACK can carry the first request bytes in the same segment. The third leg is normally not an extra wait; it is a flag set on a packet A was going to send anyway.

### Where the three-packet picture stops holding

- Closing takes four segments, not three: FIN plus ACK in each direction, because each direction is shut down separately.
- A simultaneous open, where both ends send SYN at once, also takes four, and neither end is the responder.
- TCP Fast Open (RFC 7413) puts request data in the very first SYN, using a cookie B issued during an earlier connection. The three segments still happen; the data just stops waiting for them.
- Because B commits state after packet one and before packet three, an attacker can send SYNs and never reply, filling B's connection table (a SYN flood). SYN cookies are the standard answer: B encodes the connection state into the ISN it picks, so it can validate packet three without having stored anything.

And the limit worth carrying away: three packets do not make both ends certain. If the final ACK is lost, A believes the connection is established while B does not, and no fixed number of messages fixes that, because two parties communicating over an unreliable channel can never both be sure the other is ready (the two-generals problem). Three is the smallest exchange that establishes both sequence numbers and gives every loss case a defined recovery, not a proof that the two ends agree.
