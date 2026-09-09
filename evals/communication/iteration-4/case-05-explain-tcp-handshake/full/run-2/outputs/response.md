Because each side has to tell the other where its byte numbering starts (its initial sequence number, or ISN), and telling is not enough on an unreliable network. The number has to be acknowledged. Two numbers, each acknowledged, is four messages; two of them travel in the same direction one after the other, so TCP packs them into a single segment. Four logical messages, three actual packets.

## The counting argument

TCP labels every byte it sends with a sequence number, so the receiver can put the stream back in order and notice what is missing. Neither side can just start at 0 (reason below), so each picks its own ISN and has to communicate it.

The full logical exchange is:

1. Client sends its ISN.
2. Server acknowledges the client's ISN.
3. Server sends its ISN.
4. Client acknowledges the server's ISN.

Messages 2 and 3 both go from server to client, back to back, so they ride in one segment: the SYN-ACK. That is the entire compression. The three-way handshake is a four-way handshake with the redundant packet removed, not a cleverer protocol.

Two messages cannot cover four roles. Whichever pair you pick, the server's ISN ends up unacknowledged.

## What a two-message handshake actually breaks

**The server would open connections nobody asked for.** Suppose a client's SYN gets held up somewhere in the network. The client times out, retransmits, opens the connection, transfers its data, and closes. A minute later the original delayed SYN finally arrives. With only two messages, the server answers and immediately treats the connection as live: it allocates a socket and will accept segments in the sequence range that stale SYN declared, which can include old duplicate data still drifting in from the earlier connection. With three messages, the server sends its SYN-ACK and waits in the SYN-RECEIVED state, holding the connection as pending rather than established. The client, which has no such connection, replies to the unexpected SYN-ACK with a reset, and the server discards it. This is the reason RFC 793 puts first: the three-way handshake exists mainly to stop old duplicate connection requests from causing confusion.

**The server would send data the client cannot interpret.** If the SYN-ACK is lost, a two-message server still believes it is connected and starts transmitting with sequence numbers the client has never seen. The third message makes the server's move to ESTABLISHED conditional on evidence, so a lost SYN-ACK just gets retransmitted instead.

There is a third, weaker benefit. To produce a valid final ACK, the client has to quote the server's ISN, so it must genuinely have received the SYN-ACK at the address it claimed to be at. That makes connections from a forged source address hard to open, but only while ISNs stay unpredictable. Modern stacks derive them from a secret keyed hash of the connection's addresses and ports plus a clock (RFC 6528); older ones used a simple incrementing counter and were spoofable. Treat this as a useful side effect, not a security mechanism to lean on.

## Why not agree on a fixed starting number

If both ends always began at 0, no ISN exchange would be needed and a two-message "let's talk / ok" would nearly work. The problem is that a segment from a previous connection between the same address and port pair would then be numerically indistinguishable from a segment in the current one. A packet delayed past the close of one connection could arrive during the next and be accepted as real data. Unpredictable ISNs put old segments outside the current window. That is why the number must be told rather than assumed, and therefore why a handshake exists at all.

## What three messages do not buy you

The handshake does not leave both sides certain. The client knows the server received its ISN. The server knows the client received its ISN. But the client never learns whether its final ACK arrived, and adding messages does not fix that, since each new message needs its own acknowledgment. TCP simply tolerates the gap: if the ACK is lost, the server retransmits the SYN-ACK, and the client's first data segment carries the same acknowledgment number anyway.

Two more places the "three packets, then data" picture needs refining, if either becomes relevant to you. TCP Fast Open (RFC 7413) lets a client put data in the initial SYN using a cookie saved from an earlier connection, so the round trip is not always paid. And because the server allocates state on the first SYN, an attacker can flood it with SYNs that are never completed, which is why servers use SYN cookies to defer that allocation until the third message arrives.

Next: in Wireshark, start a capture, load any web page, and filter on `tcp.flags.syn == 1`. You will see the SYN and the SYN-ACK; clear the filter and the next packet in that stream is the bare ACK that finishes the handshake.
