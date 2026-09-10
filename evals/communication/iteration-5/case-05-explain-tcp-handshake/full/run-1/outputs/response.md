Because a TCP connection carries two independent streams, one in each direction, and each direction's starting point has to be confirmed by the other side. Two messages confirm only one of them. The third packet also does a second job: it lets the server tell a live connection request from a stale one the network delivered late.

## What the handshake agrees on

TCP labels every byte it sends with a sequence number, so the receiver can reassemble pieces in order and notice what is missing. The numbering does not start at zero. Each side picks its own initial sequence number (ISN), chosen to be hard to guess and unlikely to overlap with a previous connection between the same two ports.

Because the two streams are numbered separately, there are two ISNs to settle, not one. That makes the handshake four logical events:

1. Client announces its ISN (the SYN flag, short for synchronize)
2. Server acknowledges the client's ISN (the ACK flag)
3. Server announces its own ISN (SYN again)
4. Client acknowledges the server's ISN (ACK)

Events 2 and 3 ride in a single packet, the one written SYN-ACK. Three packets, four confirmations. That compression is piggybacking, not a shortcut in the logic.

## Why two is not enough

Notice who is actually finished after two packets: the client. Once the SYN-ACK arrives, the client has its own ISN acknowledged and knows the server's, so it moves to ESTABLISHED. The third packet exists for the server's benefit.

Strip it away and the server has to declare the connection open on the strength of one packet it has never verified. Plain loss is survivable; if the SYN-ACK vanished, the client retransmits its SYN and the exchange repeats. What is not survivable is that networks deliver stale packets. A SYN from an attempt made minutes ago can sit in a queue or take a long path and arrive after the attempt it belonged to was abandoned. In a two-message design the server accepts that old SYN, allocates a connection, and starts sending data to a client that is not expecting any. If the old and new attempts share the four values that identify a connection (source IP, source port, destination IP, destination port), leftover segments from the dead attempt can land inside the live connection's sequence range and be handed to the application as real data.

The third packet is the server's test for that case. The server stays in SYN-RECEIVED until the ACK arrives. A real client sends it. A machine that made no such request has no matching connection and answers RST (reset), so the server discards the half-open connection before anything is transferred.

## Why not four

The fourth confirmation buys nothing. After sending its ACK, the client does not know whether that ACK arrived. A packet confirming it would leave the server unsure whether that confirmation arrived, and so on without end; this is the same limit as the two generals problem. No finite exchange makes both sides certain that the other is certain. TCP stops where each ISN has been acknowledged once, and lets retransmission absorb the residue: if the client's ACK is lost, the server retransmits the SYN-ACK, and the client's first data packet carries the acknowledgement again.

## The side effect that shaped security

Finishing the handshake also proves the client can receive at the address it claimed, since the third packet has to come back from there. An attacker forging source addresses can start connections but never finish them, which is what a SYN flood is: the server holds state for every half-open connection while waiting for an ACK that will never come, and the queue fills. SYN cookies remove that exposure by encoding the needed state into the server's own ISN, so nothing is stored until the ACK returns.

## Where "three is the minimum" stops holding

Three packets cost one round trip before the first application byte, since the client can attach data to its ACK. Over a link with 80 ms round-trip latency, every new connection pays 80 ms of dead time, which is most of the reason connection reuse (HTTP keep-alive, connection pools) matters as much as it does.

Three is the minimum only for two machines with no prior relationship. Given prior state you can do better. TCP Fast Open has the server issue a cookie during a normal handshake; on a later connection the client puts that cookie and its first request into the SYN, and the server acts on it immediately. QUIC merges the transport and encryption handshakes and, with a resumption ticket, sends application data in its very first packet. Both swap "prove you are current" for "present a token only a current client could hold," which buys the same protection without the extra round trip.
