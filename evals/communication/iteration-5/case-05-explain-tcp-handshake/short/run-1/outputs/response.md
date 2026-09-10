Because two messages only confirm one direction. TCP has to agree on a starting sequence number for each direction before either side can send data reliably, and each side needs proof that its own number arrived.

The Initial Sequence Number (ISN) is the number each side picks for the first byte of its own outgoing stream. Everything after is counted from there, which is how TCP detects loss, reordering, and duplicates. So there are two facts to establish, one per direction, and each one has to be acknowledged:

1. SYN, client to server: "my ISN is x."
2. SYN-ACK, server to client: "I have x, my ISN is y."
3. ACK, client to server: "I have y."

Stop after step 2 and the client knows the server received x, but the server has no idea whether y ever arrived. It would start sending data with no evidence the client can even place that data in a stream. Note that four things need saying (two ISNs, two acknowledgements) and step 2 folds two of them into a single packet, so three is the compressed form of four rather than a padded form of two.

The second reason is stale SYNs. A SYN from a long-dead connection can be delayed in the network and show up much later. With a two-message handshake the server would open a connection, allocate buffers, and start pushing data to a peer that never asked for it, with no way to find out. The third message is where the client says "that is not my connection" by replying RST instead of ACK, and the server tears the half-open connection down. Randomized ISNs plus that final ACK are what let a server tell a live peer from a replayed packet, and they also weakly confirm that whoever sent the SYN can actually receive traffic at the source address it claimed.

Three is not a count that makes the handshake certain, though. The final ACK is itself unacknowledged and can be lost; when it is, the server retransmits its SYN-ACK, and the client's first data segment carries the ACK anyway. A fourth message would just move the same gap one step later, since that ack would need its own ack. Three is the point where both sides hold enough to start sending safely, and where extra messages stop buying anything.
