### How JWT auth works

A JWT (JSON Web Token) is a signed string the server hands you after login, and that you present on every later request instead of a traditional session cookie.

A token is three base64url-encoded segments joined by dots: `header.payload.signature`.

- The header names the signing algorithm, commonly HS256 or RS256.
- The payload holds the claims: user ID, roles, an expiration time (`exp`), issued-at time (`iat`), and anything else the app needs. This part is only encoded, not encrypted, so anyone holding the token can read it. Never put secrets in here.
- The signature is a cryptographic hash of the header and payload, produced with a secret (HMAC) or a private key (RSA/ECDSA) that only the server holds. It makes the token tamper-evident: change one character of the payload and the signature no longer matches.

The flow: you log in with a username and password, the server checks your credentials, builds a JWT with your identity and claims, signs it, and sends it back. Your client stores it (a cookie, or localStorage) and attaches it to every request afterward, usually as `Authorization: Bearer <token>`. On each request, the server does not query a database. It recomputes the signature using its key, checks that it matches what is on the token, and checks that `exp` has not passed. If both hold, it trusts the claims inside and moves on.

### Why people call it "stateless"

Compare that to classic session auth: the server generates a session ID, stores a record of it (in memory, or in something like Redis) mapped to the user, and hands the client only the ID. Every request means a lookup against that store. The server is holding state about who is logged in, and that store has to be reachable from wherever the request lands.

JWTs remove that lookup. Everything needed to trust the token travels inside the token, and trust comes from a signature check rather than a database read. No server has to remember that a given token exists. That is the stateless part, and it is why JWTs are popular for systems with several backend instances or microservices: any instance holding the verification key (the same shared secret for HMAC, or just the public key for RSA/ECDSA) can verify a token on its own, with no shared session store to keep in sync.

### Can you actually log someone out?

What you heard is directionally right, and it follows straight from the same property that makes JWTs stateless. Since the server never recorded "this token is currently valid" anywhere, there is nothing to delete on logout. The token stays cryptographically valid, and the server keeps accepting it, until its own `exp` claim says it has expired, regardless of what the client does.

Deleting the token client-side (clearing the cookie or localStorage) covers the normal case, since that browser stops sending it. But if a copy of the token got out, say through an XSS bug, a proxy log, or a stolen laptop, that copy keeps working right up to expiry even after you click "log out."

So a pure, nothing-but-a-signature JWT setup really has no logout. Real systems close that gap with some combination of:

- Short-lived access tokens. Set `exp` to something like 5 to 15 minutes, so a token that should have been revoked is only a risk for that narrow window.
- Refresh tokens. Pair the short-lived JWT with a longer-lived refresh token stored server-side, one row per session. The client trades it in for new access tokens, and logout deletes that row. The already-issued access token still works until it expires naturally, but no new ones get minted after logout.
- A revocation list. Keep a small server-side store, commonly Redis, of revoked token IDs (the `jti` claim) or logged-out user IDs, and check it on every request. This closes the gap immediately, but notice what happened: the per-request state lookup that JWTs were meant to avoid is back. At that point it is a hybrid, not pure stateless auth.
- A per-user "valid since" timestamp. Store one timestamp per user, updated on logout or password change, and reject any token issued earlier than that. Cheaper than a full revocation list since it is one value per user instead of one entry per token.

Short-lived access tokens paired with a revocable refresh token is the standard production pattern, and it is essentially what OAuth2 access and refresh flows do.

Bottom line: with plain JWTs and no extra bookkeeping, you cannot force an early logout, so that part is true. But "you can't log someone out with JWTs" as a flat statement is not quite right, because nobody ships plain JWTs with zero bookkeeping for anything that needs real logout. They add a small amount of server-side state back in, on purpose, exactly where it is needed. The real tradeoff is a dial between fully stateless (fast, simple, cannot revoke early) and partially stateful (a bit more infrastructure, can revoke immediately), not a flat yes or no.
