Rotating an HS256 secret is not a swap, it is a widen-then-narrow in three phases. Every token sitting in a browser right now was signed with the old key and you have no way to reach out and re-sign it, so verification has to accept both keys for a while. Signing uses exactly one key; verification takes a list. You add the new key to the accept list everywhere, move signing to it, wait for the last old-key token to expire on its own, then drop the old key.

Nothing below changes normal expiry. People still get logged out 24 hours after their last token was issued, exactly as they do today.

## First: is this a hygiene rotation or a leak?

If it is scheduled or precautionary, do the plan below.

If the old key actually leaked (committed to git, pasted in a chat, on a stolen laptop, printed in a log), then the overlap window is the problem, not the solution: anyone holding that key can mint valid tokens for as long as you keep accepting it. In that case you either cut over hard and accept the mass logout, or you build real invalidation, which means a `tokenVersion` integer or `sessionsValidAfter` timestamp per user, embedded in the token and checked against your store on each request. That is a design change with a lookup on every request, not a config change.

Two commands worth running before you decide:

```
git log --all --oneline -- .env
git log --all -S 'JWT_SECRET' --oneline
```

## 1. Generate the new key

```
node -e "console.log(require('crypto').randomBytes(48).toString('base64url'))"
```

48 random bytes gives you comfortably more than the 256 bits HS256 requires, and base64url output contains no commas or shell-quoting hazards, which matters for step 2. If your current `JWT_SECRET` is a memorable passphrase rather than random bytes, that by itself justifies the rotation.

## 2. Make verification accept a list of keys

This is the only code change. Keep `JWT_SECRET` as the signing key so no existing call site has to move, and add a separate verify-only variable.

```js
// auth/keys.js
const signingKey = process.env.JWT_SECRET;
if (!signingKey) throw new Error('JWT_SECRET is not set');

// Verify-only keys, comma separated. Empty in steady state.
const extraKeys = (process.env.JWT_ACCEPTED_SECRETS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

// Signing key first, so the common case verifies on the first try.
module.exports = { signingKey, verifyKeys: [signingKey, ...extraKeys] };
```

```js
// auth/verify.js
const jwt = require('jsonwebtoken');
const { verifyKeys } = require('./keys');

const VERIFY_OPTS = { algorithms: ['HS256'] };

function verifyToken(token) {
  let lastError;
  for (let i = 0; i < verifyKeys.length; i++) {
    try {
      const payload = jwt.verify(token, verifyKeys[i], VERIFY_OPTS);
      if (i > 0) console.warn('jwt_verified_with_fallback_key', { keyIndex: i });
      return payload;
    } catch (err) {
      // jsonwebtoken checks the signature before exp/nbf, so these two errors
      // mean the key already matched. Trying another key cannot help.
      if (err.name === 'TokenExpiredError' || err.name === 'NotBeforeError') throw err;
      lastError = err;
    }
  }
  throw lastError;
}

module.exports = { verifyToken };
```

Three details in there that matter:

Pin `algorithms: ['HS256']`. If your current `jwt.verify` call omits it, fix that in this same change; it is the standard guard against algorithm-confusion attacks and it costs nothing.

Do not retry on `TokenExpiredError`. Signature verification runs first in `jsonwebtoken`, so an expiry error is proof the key matched, and retrying would turn a clean 401 into a confusing one.

Whatever middleware calls this should return the same 401 body regardless of which key matched or which error came back. Do not tell a client that its token was signed with a retired key.

Your `jwt.sign` call stays as it is, pointing at `signingKey`, with `{ algorithm: 'HS256', expiresIn: '24h' }`.

Before deploying, add three tests: a token signed with the fallback key verifies, a token signed with a key that is in neither slot fails, and an expired token signed with the current key still fails as expired.

## The three environment states

| Phase | `JWT_SECRET` (signs and verifies) | `JWT_ACCEPTED_SECRETS` (verify only) |
|---|---|---|
| now | old | unset |
| 1 | old | new |
| 2 | new | old |
| 3 | new | unset |

## 3. Deploy phase 1: accept both, still sign with the old key

Ship the code change with `JWT_SECRET` unchanged and `JWT_ACCEPTED_SECRETS` set to the new key. Behavior is identical to today, which is the point: this deploy is a no-op you can roll back freely.

It exists because of rolling deploys. If you skip straight to signing with the new key, instances still running the old config will reject tokens minted by instances running the new one, and your users get intermittent 401s that look random. Every process that verifies these tokens needs phase 1 before any process reaches phase 2.

If you run exactly one instance and restart it in place with a moment of downtime, you can collapse phases 1 and 2 into a single restart. If you run more than one, or you are on a platform that shifts traffic gradually, do not.

## 4. Phase 2: move signing to the new key

Set `JWT_SECRET` to the new key and `JWT_ACCEPTED_SECRETS` to the old key. Restart or redeploy. New logins now get new-key tokens; every token already issued keeps working until it expires normally.

Note the timestamp when the last instance finishes rolling. That is when your clock starts, not when you began the deploy.

## 5. Wait out the longest token lifetime

At minimum 24 hours from the moment in step 4, plus a few hours of margin for clock skew and stragglers. Call it 30 hours if you want a round number.

The real signal is the `jwt_verified_with_fallback_key` line from step 2. When it stops appearing, no live token is signed with the old key any more. Waiting on the log beats waiting on the clock, because the clock assumes you know every token lifetime, and step 6 depends on that being true.

Before you trust the 24-hour figure, run `grep -rn "jwt.sign(" src/` (adjust the path) and read every `expiresIn` you find. The window is set by the longest-lived thing signed with `JWT_SECRET`, not by your login token. Refresh tokens, password-reset links, email-verification links, invite links, and service-to-service tokens are the usual surprises, and any one of them at 7 or 30 days turns this into a 7 or 30 day wait.

## 6. Phase 3: drop the old key

Unset `JWT_ACCEPTED_SECRETS`, redeploy, and delete the old value from wherever you store secrets.

Do not skip this. An accept list you never prune means you did all the work of a rotation and kept all of the risk. Put a dated ticket on it in the same session you start phase 1, because this is the step everyone forgets.

While you are here, add `keyid: 'v2'` to your `jwt.sign` options. It does nothing for this rotation, since tokens already issued carry no `kid` header, but it lets the next rotation select the key directly instead of trying each one in turn.

## Things that will bite you

`dotenv` reads `.env` once at process start. Editing the file on a running server changes nothing; you need an actual restart. Confirm the new values are live by logging a fingerprint at boot, for example the first eight characters of a SHA-256 of each key, never the keys themselves.

Enumerate every verifier before phase 1, not during it. A second API, a background worker, a websocket or socket.io handshake, an Nginx or gateway JWT check, framework middleware, and your CI test fixtures all count.

Two HMAC verifications per request instead of one is microseconds. It is not worth optimizing and not worth worrying about.

Storing the signing key in `.env` on the box means it is readable by anything that reads the filesystem, and it lands in every backup and image. Since you are already touching this, moving both variables into a secret manager is a small marginal step.

Longer term, the reason "rotate the key without logging anyone out" is awkward is that a stateless 24-hour token cannot be withdrawn. Short access tokens (10 to 15 minutes) plus a revocable refresh token turns both key rotation and "log this one user out now" into routine operations.

## What I could not verify

I have not seen your code, so the snippets above are the right shape, not a drop-in. Your module layout, middleware, and variable names will differ.

I do not know whether your current `jwt.verify` call pins `algorithms`, whether it swallows errors in a way that would hide the fallback path, or how many separate services verify these tokens. Check each of those.

I do not know whether you issue refresh tokens or any other JWT from the same `JWT_SECRET`. If you do, step 5 is governed by that longer lifetime and the whole timeline stretches accordingly.

I also do not know whether this rotation is precautionary or a response to exposure, which is the one thing that changes the plan rather than just its schedule.
