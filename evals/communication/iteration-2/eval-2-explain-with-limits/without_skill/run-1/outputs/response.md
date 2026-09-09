JWT auth works by having the server issue a signed token instead of a session ID. Here's the mechanism, then why people call it stateless, then a direct answer to the logout question, since that one deserves more than yes or no.

**The mechanism**

A JWT is three base64url-encoded parts joined by dots: `header.payload.signature`. The header names the signing algorithm (commonly HS256, an HMAC with a shared secret, or RS256, an RSA signature with a public/private key pair). The payload holds claims: things like the user ID, role, an issued-at time, and an expiration time. Something like:

```json
{
  "sub": "user_123",
  "role": "admin",
  "iat": 1757260800,
  "exp": 1757261700
}
```

The signature is computed over the header and payload using the server's key. That's what makes the token tamper-evident: change one character of the payload and the signature no longer matches.

The flow: a user logs in with a password, the server checks it against the database, builds a JWT with whatever claims it wants to assert, and signs it. The client stores that token and sends it back on every request, typically as `Authorization: Bearer <token>`. The server verifies the signature and checks the expiration claim on each request. If both pass, it trusts the payload, no other lookup required.

**Why "stateless"**

Compare that to classic session auth: the server generates a random session ID, stores the actual session data (user ID, role, etc.) in a database or something like Redis, and hands the client only the ID. Every request means a lookup: does this session ID exist, and what's attached to it? That lookup, and the storage behind it, is server-side state, and it has to be kept consistent across every server that might handle a request.

A JWT carries its own state with it instead of leaving it on the server. Verifying one is pure computation (recompute the signature, compare timestamps), not a database read. Any server holding the signing key can verify any valid token independently, with no shared session store and no coordination between servers. That's the stateless property, and it's a real win for horizontal scaling.

**Is the logout thing true?**

Yes, in the way people usually mean it. Because the server never records which tokens it has issued, there's no list to remove a token from. Logging out can clear the token from the browser, which stops that browser from sending it again, but a copy of that token sitting anywhere else (a proxy log, an intercepted request, a browser extension) keeps working exactly as before. There is no way to reach into a live JWT and kill it early, because doing that requires the server to track issued tokens, which is precisely the state a stateless design set out to avoid.

Nobody ships this raw, though. The standard fixes:

- **Short expirations.** Five to fifteen minutes is typical for an access token, so a leaked or stale one is only useful briefly.
- **Refresh tokens.** Pair the short-lived JWT with a longer-lived refresh token that lives in a database. Logout revokes the refresh token; the access token just ages out on its own shortly after.
- **A revocation list for urgent cases.** A small server-side store (Redis, keyed by the token's `jti` claim) checked on each request, for situations like a compromised account that can't wait for expiry. This works, but it puts state back on the server for exactly the tokens that need it.
- **A per-user "valid since" marker.** Store a timestamp or version number per user, and reject any token issued before it. Bumping it on logout or password change invalidates every outstanding token for that user in one move.

So: stateless describes how the server verifies a request, not a claim that the token is powerless or that logout is a solved problem. The tradeoff is real, and every production system using JWTs handles it with one of the patterns above rather than pretending it isn't there.
