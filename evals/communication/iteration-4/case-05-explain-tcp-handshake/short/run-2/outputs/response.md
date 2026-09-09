Because a TCP connection is full duplex: two independent data streams, one in each direction, each with its own sequence numbering. Each side picks a random initial sequence number (ISN), and the other side has to both learn it and confirm it. That is four logical events, and two of them fit in one packet, which leaves three.

1. Client sends `SYN` with `seq=x`, announcing its ISN.
2. Server replies `SYN-ACK`: `seq=y` announces the server's ISN, `ack=x+1` confirms it received the client's. Two events, one packet.
3. Client sends `ACK` with `ack=y+1`, confirming the server's ISN.

After step 3, each side knows its own numbering reached the other. A two-message exchange cannot give you that.

**What breaks with only two messages**

The server's ISN goes unconfirmed. If the `SYN-ACK` is lost, the client never learns the server's sequence numbers and does not believe a connection exists, while the server considers itself established and may start sending into a void. The third packet is what closes that gap.

Old duplicate SYNs. Suppose a `SYN` from an earlier connection attempt gets delayed in the network and arrives long after the client gave up. With a two-way handshake the server accepts it, allocates state, and believes it has a live peer that isn't there, and stale data from that old incarnation can be taken as fresh. With three, the server's `SYN-ACK` puts the question back to the client, which has no matching connection and answers `RST`, and the server returns to `LISTEN`. This is the specific justification RFC 793 gives.

The third packet also does real security work: the client must echo back a number it could only have learned by actually receiving the server's packet, which makes blind off-path spoofing hard. Worth naming the limit, though, since it is not authentication. Anyone who can read the packets sees the ISN, so this stops off-path guessing, not an on-path attacker.

**Why not four?** The server's acknowledgment of the client's SYN and the server's own SYN travel the same direction at the same moment, so they piggyback into one segment. Three is the minimum for mutual, acknowledged agreement on two numbers.

One honest caveat on "three is enough": no finite exchange makes both sides certain the other agrees (the two generals problem). TCP settles for each ISN being acknowledged once and leans on retransmission and timeouts for everything after.

The cost is one round trip before data can flow. The third packet usually carries the client's first request, so it is not a wasted packet, but the RTT is real. That is what TCP Fast Open (RFC 7413) trims, by letting data ride on the SYN using a cookie from a prior connection, and what QUIC attacks by merging the transport and TLS handshakes into one.
