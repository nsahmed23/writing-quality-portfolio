JWT auth works by putting proof of who the user is directly inside the token, instead of making the server remember who's logged in.

## The token itself

A JWT (JSON Web Token) is three chunks of text joined by dots: `header.payload.signature`.

- **Header**: says which algorithm signed the token, e.g. HMAC-SHA256 or RSA.
- **Payload**: the "claims", the actual data such as user ID, role, and an expiration time (`exp`). This part is base64-encoded, not encrypted, so anyone holding the token can read it. Don't put secrets in it.
- **Signature**: a cryptographic hash of the header and payload, produced with a key only the issuing server holds. With a symmetric algorithm (HMAC) one shared secret both signs and verifies; with an asymmetric one (RSA, ECDSA) a private key signs and a matching public key verifies, which lets other services check a token without ever holding the secret that created it. Either way, changing one character of the payload breaks the signature match, so the token can't be tampered with unnoticed.

## The login flow

1. User submits credentials.
2. Server checks them against its user store, as usual.
3. If valid, the server builds a token containing whatever claims it wants to remember about this user, and signs it.
4. The client stores the token and attaches it to every later request, usually as `Authorization: Bearer <token>`.
5. On each request, the server recomputes the signature and checks it matches, and checks `exp` hasn't passed. If both hold, the request is authenticated using the claims in the payload, no further lookup needed.

## Why people call it "stateless"

Compare it to the older cookie-session model: the server generates a random session ID, stores the session's data (user ID, roles, etc.) in server-side memory or something like Redis, and hands the client only the ID. Every request, the server looks that ID up to find out who's asking. The server is holding state, a table mapping session IDs to users.

With a JWT, the server stores nothing about the session. The token carries its own proof (the signature) and its own data (the claims), so verifying it is pure computation, recompute a hash, compare it, check a timestamp, no database or shared session store involved. Any server instance that holds the verification key (the shared secret, or just the public half of a key pair) can verify any token on its own. That's why JWTs are popular in load-balanced or multi-service setups: no server has to share session storage with the others.

"Stateless" describes the server, not the absence of state. The state (who this is, what they're allowed to do, until when) didn't disappear, it moved into the token. That's what makes it portable, and it's also exactly why revoking it early is awkward: nothing is tracking it centrally anymore.

## Can you actually log someone out?

The claim is accurate for a bare JWT with no extra machinery, and inaccurate as a description of how most real systems implement JWT auth.

The mechanism behind the claim: since the server never stored anything about issued tokens, there's no record to delete on logout. A logout button can delete the token from the browser, but if the same JWT reaches the server again from anywhere else, cached, replayed, whatever, it still passes signature verification and still hasn't hit its `exp` time, so it's accepted. Nothing server-side changed, because nothing server-side was tracking that token to begin with. That's the real basis for "you can't log out with JWTs": revocation before expiry isn't part of the base design.

In practice, systems add one of these to get real logout back, and each one trades away some of the statelessness that was the point of using JWTs:

1. **Short-lived access tokens plus a refresh token.** The JWT itself expires in minutes. A separate, longer-lived refresh token, which is stored server-side, is what the client uses to get a new JWT. Logout revokes the refresh token in the database. The short-lived JWT can still work until it naturally expires, but that window is small.
2. **A revocation list.** Give every token a unique ID (the `jti` claim) when it's issued. The server keeps a store, Redis or a database, of IDs logged out before their natural expiry, and checks each incoming token against it. This works, but it puts a lookup back on every request, which cancels out much of the reason to use JWTs.
3. **A version check.** Store a `tokenVersion` or `passwordChangedAt` value per user, embed the current value in the token when it's issued, and compare it to the live value on each request. Logging out, or changing a password, bumps the stored value, so old tokens fail the comparison. Cheaper than a full revocation list if that value is cached, but it's still a state check bolted onto a design that was meant not to need one.

So the part you heard that's true: a pure JWT can't be individually invalidated before it expires. The part that's an overstatement: "JWT auth" as actually deployed almost always includes one of the three mechanisms above, so blanket claims that you can't log out are describing the textbook version, not the systems people actually ship.
