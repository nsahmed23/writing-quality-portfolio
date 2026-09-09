Because TCP is bidirectional, and each direction has its own sequence number that has to be both delivered and confirmed.

A TCP connection is really two independent byte streams, one per direction. Each stream starts at an initial sequence number (ISN), a starting count both ends use to order bytes and notice missing ones. For the connection to work, each side must learn the other's ISN, and must know its own ISN arrived.

That is four facts, not three:

1. Client sends its ISN (SYN).
2. Server acknowledges it.
3. Server sends its ISN (SYN).
4. Client acknowledges it.

Steps 2 and 3 ride in the same segment, the SYN-ACK, because the server has both things to say at once. So four logical steps compress into three packets. Three is not a magic number; it is four minus one piggyback.

Cut it to two and the server's ISN goes unacknowledged. The server would have to assume its SYN-ACK arrived and start sending data. If that packet was dropped, the client never learned the server's sequence numbers, so it rejects the data (typically with a reset) while the server has already burned buffers and airtime on it.

The second reason is stale duplicates. An old SYN from a long-dead connection can linger in the network and show up late. With two messages, the server accepts it, allocates state, and sits half-open. With three, the client that never sent it answers with RST instead of ACK, and the server tears it down. That was the original argument in RFC 793.

The handshake also carries option negotiation (MSS, window scaling, SACK, timestamps), and each side has to both offer and confirm those before data flows.

One limit worth knowing: three messages do not make both ends certain. No finite exchange can, which is the two generals problem. The client is confident after packet 2, the server after packet 3, and the server can still be wrong if the client dies right after sending it. TCP settles for every ISN being acknowledged exactly once, which is the cheapest thing that actually works.
