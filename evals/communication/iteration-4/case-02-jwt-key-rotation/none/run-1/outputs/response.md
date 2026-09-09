Swapping `JWT_SECRET` in place logs everyone out, because every unexpired token was signed with the old secret and `jwt.verify` has nothing left to check it against. The fix is an overlap window: every verifier learns the new key *before* anything signs with it, and the old key stays accepted for one full token lifetime after the switch.

Five steps. The ordering between steps 2 and 3 is the part that breaks production if you reverse it.

I have not seen your repo, so the file paths and helper shape below are a sketch to adapt. Step 0 tells you what you actually have.

## 0. Inventory (do this first, it sets the wait in step 4)

```bash
grep -rn "JWT_SECRET\|jwt.sign\|jwt.verify\|expiresIn" src/ --include="*.js" --include="*.ts"
```

Three things you are looking for:

1. **Every call site.** If `jwt.verify` is called in more than one place (auth middleware plus a socket handshake plus an admin route is the usual shape), all of them go through the helper in step 2, or the ones you miss will reject new tokens.
2. **Anything else signed with the same secret.** Password reset links, email verification links, signed webhook payloads, and invite tokens are commonly minted with the same `JWT_SECRET` and a much longer expiry. If a 7-day reset link exists, your overlap window is 7 days, not 24 hours.
3. **Every process that verifies.** Multiple app instances, a background worker, a gateway, a second service sharing the secret. Each one needs step 2 before any one of them gets step 3.

## 1. Generate the new key

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

32 bytes is the right size for HMAC-SHA256. Keep the old secret; you need it for the next three steps.

## 2. Teach every verifier both keys, keep signing with the old one

This deploy is deliberately invisible to users. Nothing about token issuance changes; you are only widening what gets accepted.

```js
// auth/keys.js
const KEYS = JSON.parse(process.env.JWT_KEYS || '{}');  // {"k1":"<old>","k2":"<new>"}
const ACTIVE_KID = process.env.JWT_ACTIVE_KID;
const LEGACY_SECRET = process.env.JWT_SECRET;           // verifies tokens minted before this deploy

if (!KEYS[ACTIVE_KID]) {
  throw new Error(`JWT_ACTIVE_KID=${ACTIVE_KID} is not present in JWT_KEYS`);
}

function signingKey() {
  return { kid: ACTIVE_KID, secret: KEYS[ACTIVE_KID] };
}

function verifyingKey(kid) {
  if (!kid) return LEGACY_SECRET || null;  // no kid header means pre-rotation token
  return Object.prototype.hasOwnProperty.call(KEYS, kid) ? KEYS[kid] : null;
}

module.exports = { signingKey, verifyingKey };
```

```js
// auth/verify.js
const jwt = require('jsonwebtoken');
const { verifyingKey } = require('./keys');

function verifyToken(token) {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded) throw new Error('malformed token');

  const kid = decoded.header.kid;
  const secret = verifyingKey(kid);
  if (!secret) throw new Error('unknown key id');

  const claims = jwt.verify(token, secret, { algorithms: ['HS256'] });
  logger.info({ kid: kid || 'legacy' }, 'jwt verified');  // step 4 depends on this line
  return claims;
}
```

Two things in there are load-bearing:

- `jwt.decode` does not verify anything, and `kid` comes from the attacker-controlled part of the token. Use it only as a lookup into a fixed map, never to build a file path or derive a key. An unknown `kid` is a hard reject.
- Pin `algorithms: ['HS256']` explicitly. Current `jsonwebtoken` narrows the accepted set by key type on its own, but pinning is the actual guarantee and it is one line.

Env for this deploy, with the old secret intentionally appearing twice:

```
JWT_SECRET=<old secret, unchanged>
JWT_KEYS={"k1":"<old secret>","k2":"<new key from step 1>"}
JWT_ACTIVE_KID=k1
```

If embedding JSON in `.env` fights your loader, use `JWT_KEY_K1=` and `JWT_KEY_K2=` and assemble the map at boot instead.

Ship it and confirm nothing moved: hit an authenticated endpoint with a token you were already holding before the deploy, and log in fresh to get a new one. Both must work. Wait until every instance is running this build before continuing. On a rolling deploy that means all instances healthy on the new revision, not just the first.

## 3. Flip the signing key

One variable, then restart:

```
JWT_ACTIVE_KID=k2
```

And in your login route, sign through the helper so the header carries the id:

```js
const { signingKey } = require('./auth/keys');
const { kid, secret } = signingKey();

const token = jwt.sign(payload, secret, {
  algorithm: 'HS256',
  expiresIn: '24h',
  keyid: kid,          // jsonwebtoken writes this as the `kid` header
});
```

Verify: log in, decode the token with `jwt.decode(t, { complete: true })`, and confirm the header says `"kid":"k2"`. Then confirm a token issued yesterday still works.

Rollback here is free. Set `JWT_ACTIVE_KID=k1`, restart, done; both keys are still accepted, so no token issued in either direction breaks.

## 4. Wait out the token lifetime

The last token signed with `k1` was minted a moment before the step 3 restart finished, so it lives for 24 hours past that point. Earliest safe removal is **24h after the last instance flipped**, plus a margin for clock skew and slow retries. Round to 26 hours, or just do step 5 the following morning.

If step 0 turned up anything with a longer expiry signed by the same secret, that number replaces the 24h.

Do not rely on the clock alone. That `kid` log line from step 2 is the real signal: filter for `kid: k1` and `kid: legacy` and confirm the count has been flat at zero for several hours. If it has not, something is still issuing or holding old tokens and you want to know why before you break them.

## 5. Retire the old key

```
JWT_KEYS={"k2":"<new key>"}
JWT_ACTIVE_KID=k2
```

Delete `JWT_SECRET` entirely, and delete the legacy branch in `verifyingKey`. Then remove the old value everywhere it lives: your local `.env`, other developers' `.env` files, CI/CD secrets, the deployment platform's config, your password manager, and any staging environment that shares it. A rotated key still sitting in CI is not rotated.

This is the only irreversible step, which is why it goes last.

---

**If you are rotating because the secret leaked, this whole procedure is wrong.** The overlap window is a feature when the goal is hygiene and a liability when the goal is containment; it keeps forged tokens working for another 24 hours. In that case cut over hard, accept the mass logout, and treat the re-login as the point. If you genuinely cannot log everyone out, the tool is per-user revocation, not key overlap: store a `tokenVersion` integer on each user row, put it in the claims, bump it to invalidate, and compare on each request. That costs a lookup per request unless you cache it, which is why it is not the default answer.

**Minimal-diff variant.** If you would rather not introduce `kid` at all, try both keys in sequence:

```js
function verifyToken(token) {
  try {
    return jwt.verify(token, NEW_SECRET, { algorithms: ['HS256'] });
  } catch (err) {
    if (err.name !== 'JsonWebTokenError') throw err;  // let expiry errors through unchanged
    return jwt.verify(token, OLD_SECRET, { algorithms: ['HS256'] });
  }
}
```

Same five-step ordering, same wait. It handles your existing no-`kid` tokens for free and is a smaller change. What you give up is observability: you cannot cheaply distinguish "signed with the old key" from "invalid token," so step 4 becomes clock-watching instead of metric-watching. Note the rethrow, since retrying a `TokenExpiredError` against the old key just produces a more confusing error.

## What I could not verify

I do not have your code, so all of the following is assumed rather than checked: that `jwt.sign` and `jwt.verify` are centralized rather than scattered across routes; that 24h is the expiry in code and not only in the config you remember; that nothing else in the app signs with `JWT_SECRET`; your `jsonwebtoken` major version (the `keyid` sign option and `algorithms` verify option are stable across v8 and v9, but v9 tightened default algorithm handling); and how many processes verify these tokens. The step 0 grep answers the first three in about two minutes, and the answers can change the wait in step 4.

## Worth doing afterward

The reason this takes two days is the 24h expiry. If you move to short access tokens (15 minutes) plus refresh tokens, the same procedure completes in about twenty minutes, and you get real revocation as a side effect. Not required now, but the next rotation will be much cheaper for it.
