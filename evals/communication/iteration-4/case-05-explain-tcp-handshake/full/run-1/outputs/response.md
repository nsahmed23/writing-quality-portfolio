TCP carries two independent byte streams, one in each direction, and each stream's starting number has to be both announced and confirmed. That is four events. Two of them travel the same direction at the same moment, so they share a packet, and you see three.

A two-way handshake would be enough if data only ever flowed one way. It is not enough for a connection where both sides can send.

## The four events, packed into three packets

TCP numbers every byte it sends so the receiver can detect loss, discard duplicates, and reassemble segments that arrived out of order. The numbering starts at an initial sequence number (ISN), which each side picks for its own outgoing stream, randomly rather than at zero.

For each direction, two things must happen: the owner announces its ISN, and the peer confirms it received that ISN. Two directions, two events each:

1. Client announces its ISN. This is the `SYN` packet (SYN for "synchronize sequence numbers").
2. Server confirms the client's ISN.
3. Server announces its own ISN.
4. Client confirms the server's ISN.

Events 2 and 3 both travel from server to client, and the server knows both facts at the same instant, so TCP puts them in one segment with both flags set: the `SYN-ACK`. Four logical events, three packets on the wire. "Three-way" is the packet count; the structure underneath is four-way.

(The confirmations acknowledge ISN + 1, not ISN, because a SYN occupies one sequence number even though it carries no data.)

## What breaks if you stop at two

Say you send `SYN`, get `SYN-ACK` back, and call the connection open. Three specific things go wrong.

**The server never learns that its own ISN arrived.** Notice the asymmetry after two packets: the client knows its SYN got through, because the SYN-ACK acknowledged it. The server knows nothing. If that SYN-ACK was lost, the server believes it has an open connection with a peer that has never heard of it, and starts sending bytes numbered from a starting point the client does not have. The client answers `RST` (reset, meaning "I have no such connection"), and the connection dies. With three packets, the absent third one is the server's signal to retransmit the SYN-ACK, so one lost packet costs a retransmission instead of a failed connection.

**An old, delayed SYN can open a connection nobody asked for.** This is the original reason, from Tomlinson's 1975 work on sequence numbers and then RFC 793 (now RFC 9293). Networks delay and reorder; a SYN from a connection that ended minutes ago can sit in a queue or circle a routing loop and show up late. In a two-packet design the server treats it as a fresh request, allocates buffers, and considers itself connected, with no mechanism for the client to object, and old data segments trailing behind that SYN can then be accepted as valid. With three packets, the server's SYN-ACK reaches a client that has no such connection pending, the client replies RST, and the stale half-open connection is torn down. The third packet is what gives the client the chance to disown the request. Randomized ISNs help here too: sequence numbers from a dead connection are unlikely to fall inside a new connection's acceptable window.

**The server commits resources to an address it has not verified.** Source addresses in IP packets are not checked by the network, so one spoofed packet would buy a fully established connection with buffers attached. The third packet is evidence that whoever sent the SYN can actually receive traffic at the address it claimed, since that packet must carry the server's ISN, which was only ever sent to that address. It is evidence, not proof: an attacker who can observe the return path can still complete it. This is also exactly why SYN flooding works the way it does. The attacker sends SYNs and never sends the third packet, filling the server's table with connections stuck in `SYN_RECEIVED`. The standard defense, SYN cookies, has the server encode the connection state inside its own ISN and allocate nothing at all until the third packet comes back carrying that number.

## Why not four, then, or five

Four would be correct, just wasteful, since combining the server's confirmation with the server's announcement costs nothing. TCP does spend four packets when both ends open at once (a simultaneous open: both send SYN, both answer SYN-ACK). That case is a good check on the model, because it shows the three-packet form is a compression of a four-step structure rather than the structure itself.

Going past four buys nothing, and this is the part worth stating precisely. After the third packet, the client still does not know whether the server received its ACK. A fourth packet would leave the server not knowing whether the client received the fourth, and so on without end. That is the Two Generals problem: over a channel that can lose messages, no finite exchange gives both parties certainty. TCP does not solve it and does not try. It stops at the point where each side holds the guarantee it needs in order to start sending, and hands the leftover uncertainty to timers and retransmission. If the third packet vanishes, the server retransmits its SYN-ACK; the client's first data segment carries an ACK anyway. Traffic resolves the ambiguity, not more handshake.

## Where this simple picture needs refining

- The third packet is not necessarily wasted overhead. The protocol permits the client to put data in it, and TCP Fast Open (RFC 7413) goes further, allowing data in the very first SYN using a cookie from a previous connection to the same server. Most stacks send a bare ACK simply because the application usually has not written anything yet.
- The handshake costs one full round trip before any data moves, which is the whole reason QUIC folds transport setup and encryption setup into a single exchange. TLS 1.3 over TCP still pays the TCP round trip and then its own on top.
- Closing takes four packets (`FIN`, `ACK`, `FIN`, `ACK`), not three, because the two directions shut down independently: one side can stop sending while the other keeps going, so there is usually nothing to piggyback. When both sides are done at the same time, implementations do combine the middle two and it collapses to three, the same way the open does.

## Watch it happen

Open Wireshark, start a capture, load any web page, then apply the display filter `tcp.flags.syn == 1`. Every connection start appears as a pair: `[SYN]`, then `[SYN, ACK]`. Click one, clear the filter, and the next packet in that conversation is the bare `[ACK]` with length 0 that completes the handshake.
