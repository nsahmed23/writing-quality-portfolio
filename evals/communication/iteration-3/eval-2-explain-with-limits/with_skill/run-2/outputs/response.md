A JWT (JSON Web Token) is a signed, self-contained piece of data the server hands the client after login, and the client hands back on every later request instead of re-entering credentials.

## What's inside a JWT

A JWT is three base64url-encoded segments joined by dots: `header.payload.signature`.

- **Header**: metadata, mainly which signing algorithm was used (e.g., HS256, RS256).
- **Payload**: the claims, plain data like user ID, roles, and an expiration timestamp (`exp`). This part is encoded, not encrypted, so anyone holding the token can read it; never put secrets in it.
- **Signature**: computed over the header and payload using either a secret key that every verifying server must share (HMAC algorithms, like HS256) or a private/public key pair, where only the private key can sign and anyone holding the public key can verify (RSA or ECDSA, like RS256). This is what makes the token tamper-evident: change one character of the payload and the signature no longer matches it.

## The login-to-request flow

1. Client sends credentials (username and password) to a login endpoint.
2. Server verifies them, builds a JWT containing the user's claims, signs it, and returns it.
3. Client stores the token (memory, a cookie, or localStorage) and attaches it to every request afterward, usually as an `Authorization: Bearer <token>` header.
4. Server checks the signature and the `exp` claim on each request. If both check out, it trusts the claims in the payload directly; no database lookup is needed to know who's asking.

## Why people call it stateless

Compare it to classic session auth. There, the server generates a random session ID, stores the actual user data (id, roles, and so on) server-side, in memory, in Redis (a fast in-memory data store), or in a database, and gives the client only that ID, usually in a cookie. Every request forces a lookup: the server takes the ID, checks its store, and reconstructs who the user is. That store is the "state," and it has to be reachable from every server instance handling requests, which is why load-balanced session auth traditionally needs sticky sessions (always routing one user back to the same server) or a shared cache.

A JWT skips that lookup. The claims travel inside the token itself, and the signature is what lets the server trust them without checking anywhere else. Any server holding the same secret, or the matching public key, can verify a token on its own, with no shared session store involved. That is specifically what "stateless" means here: the verification step needs no server-side session state. The server is still stateful in ordinary ways, it still has a user database, for instance; it is just that authenticating a request doesn't touch it.

## The logout question

What you've heard has a real mechanism behind it, but "you can't log someone out with JWTs" as a flat statement overstates it.

The precise version: a JWT is valid, by signature and expiration alone, until its `exp` timestamp hits. If the server's entire check is "does the signature match, has it expired," there is nothing that lets it invalidate one specific token early. Clearing the token from the client, logging out in the UI, stops that client from sending it, but the token itself is still cryptographically good. If a copy exists elsewhere (a stolen device, an intercepted request), it keeps working until it expires. That is a direct consequence of statelessness, not a coincidence: the same "no lookup needed" property that makes JWTs cheap to verify is exactly what removes the one place a server would normally flip a "revoked" flag.

What production systems do about it, in roughly increasing order of how much statelessness they trade away:

- **Keep access tokens short-lived.** Expire the JWT in 5 to 15 minutes. Logout still doesn't revoke it, but the exposure window if it leaks is small and bounded.
- **Pair it with a server-side refresh token.** The JWT itself stays short-lived; a separate, longer-lived refresh token (usually just a random string with no embedded data, unlike a JWT) is stored server-side in a database. The client uses the refresh token to get new JWTs as old ones expire. Logout deletes that refresh token row. The current JWT keeps working until it naturally expires, minutes at most, but nothing new can be issued after that. This is the most common pattern in production systems.
- **Run a revocation check.** The server keeps a small store, often Redis, of revoked token IDs (the `jti` claim) or a per-user "anything issued before this timestamp is invalid" cutoff, and checks it on every request alongside the signature. This gives real, immediate logout, at the direct cost of reintroducing the per-request lookup JWTs were meant to avoid.

Put plainly: instantly revoking one already-issued JWT with zero extra infrastructure is genuinely impossible, and that part of what you heard is true. But real systems don't ship bare JWTs where real logout matters; they add back a small, targeted piece of state (a refresh-token store or a revocation check) and accept a short, bounded exposure window on the access token itself. "Can't log out" is what happens when that extra piece is skipped, not an unavoidable property of JWTs themselves.