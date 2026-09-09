JWT auth works like this:

1. **Login**: You send credentials to the server.
2. **Token issuance**: The server verifies them, then builds a JWT containing claims (user ID, roles, expiration time, etc.), signs it with a secret key (HMAC) or private key (RSA/ECDSA), and sends it back to you.
3. **Storage**: The client holds onto the token (cookie, localStorage, memory).
4. **Requests**: The client attaches the token to each request, typically in the `Authorization: Bearer <token>` header.
5. **Verification**: The server checks the signature against its key. If it's valid and not expired, the request is authenticated. No database lookup is required.

A JWT is three base64url-encoded segments joined by dots: `header.payload.signature`. The header and payload are just JSON, readable by anyone who intercepts the token; they're encoded, not encrypted. The signature is the part that matters for trust: it proves the token was issued by someone holding the secret key and hasn't been altered since.

**Why "stateless"**: Traditional session auth has the server keep a table of active session IDs somewhere (memory, Redis, a database) and look up each incoming session ID against it. JWT auth skips that lookup. Everything needed to authenticate a request travels inside the token itself, and validity is checked by math (recomputing the signature), not by asking a data store "is this still valid?" The server doesn't have to remember who's logged in. That's the statelessness people mean: no server-side session store is required to verify a request.

**On logout**: what you heard is basically correct, and it's the real trade-off of pure JWT auth. Because the server never stored the token to begin with, it has no built-in way to un-issue it. A JWT stays valid until it expires, full stop. Clearing it from the browser stops your own client from sending it, but if a copy exists anywhere else (stolen, cached, logged in a proxy), that copy is still perfectly valid until expiry, no matter how many times you click "log out."

That's rarely acceptable on its own, so real systems add a small amount of state back in. The common patterns:

- **Short-lived access tokens plus refresh tokens**: Access tokens expire in minutes; a longer-lived refresh token, checked server-side, is used to mint new ones. Revoke the refresh token and no new access tokens get issued, but any already-issued access token is still live until its short expiry runs out.
- **Denylist**: Keep a server-side list (often Redis, keyed by the token's `jti` claim) of tokens revoked early, and check incoming tokens against it. This works, but it's exactly the lookup JWTs were meant to avoid, just smaller and cheaper than a full session store.
- **Token versioning**: Store a version number or "valid since" timestamp per user in the database. Put that version in the token and compare it on every request. Bump the stored version on logout or password change, and every outstanding token for that user stops validating immediately.

So: "stateless" accurately describes how a JWT gets verified, not a promise about revocation. If your app needs logout to take effect immediately (banking, admin tools, anything security-sensitive), you need one of these stateful mechanisms, or you accept a short expiry window as the maximum blast radius.
