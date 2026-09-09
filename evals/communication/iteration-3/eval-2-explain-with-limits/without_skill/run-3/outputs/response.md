JWT auth works differently from classic session auth in one key way: the server doesn't keep a record of who's logged in.

Here's the flow. A user logs in with valid credentials, and instead of creating a session and storing it somewhere, the server creates a JWT, a signed token, and hands it back to the client. That token is a string with three base64url-encoded parts separated by dots:

- **Header**: which signing algorithm was used (e.g., HS256 or RS256) and the token type
- **Payload**: the actual claims, things like user ID, role, and expiration time (`exp`). This part is only encoded, not encrypted, so anyone holding the token can read it; don't put secrets in it
- **Signature**: the header and payload run through a cryptographic signing function, using a secret key (HMAC) or a private key (RSA/ECDSA)

The client stores the token (localStorage, a cookie, memory) and sends it back on every request, typically as `Authorization: Bearer <token>`. To validate it, the server recomputes the signature with its own key and checks it matches, then checks `exp` hasn't passed. That's it: no database or session store involved. If the signature checks out, the server trusts the claims inside.

That's what "stateless" means here. Classic session auth needs the server to generate a random session ID, store a record mapping that ID to a user (in memory, Redis, a database), and look up that record on every request; that's server-side state. A JWT carries its own proof of validity, so any server holding the verification key can check it without touching shared storage. That's also why JWTs are popular in horizontally scaled or multi-service systems: no sticky sessions, no shared session store to keep in sync.

Now, the logout question: yes, that's true, and it's the real cost of being stateless. Since the server never tracked which tokens it issued, there's nothing to delete when you "log out." A JWT is valid wherever it's presented until its `exp` timestamp passes, period. If a token gets stolen (XSS, a compromised device), deleting it from the legitimate client's storage does nothing: the stolen copy still works until it expires on its own.

Worth separating two things people conflate. Client-side logout (deleting the token so your own browser stops sending it) always works fine. Server-side revocation (making that specific token stop being valid everywhere, immediately) is what pure JWTs can't do.

In practice, almost nobody ships pure stateless JWTs for anything that needs real revocation. The standard fixes all quietly bring a little state back:

- **Short-lived access tokens + refresh tokens**: the JWT expires in minutes; a longer-lived refresh token, stored server-side so it can be revoked, is used to mint new ones. Logout kills the refresh token; a stolen access token is only useful for the few minutes until it expires anyway.
- **A revocation list**: keep a small server-side list of revoked token IDs (the `jti` claim) or user IDs, and check incoming tokens against it. It's a lookup again, just a much smaller and cheaper one than a full session store.
- **Token versioning**: store a "valid since" version or timestamp per user, bump it on logout or password change, and reject any token whose `iat` predates it.

So "stateless" is really a spectrum. A pure JWT, no extra bookkeeping, genuinely can't be revoked early; that's not a myth. Real systems almost always add one of the above to get logout back, which trades away some of the purity for the safety property they actually need.