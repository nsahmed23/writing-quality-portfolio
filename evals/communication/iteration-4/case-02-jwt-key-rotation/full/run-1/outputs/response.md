Rotate in three moves: ship code that verifies against two keys, then switch which key signs, then delete the old key once every token it signed has expired. Nobody gets logged out because the old signature stays acceptable for a full 24 hour token lifetime.

One condition before you start: if you are rotating because the old secret leaked, this graceful version keeps the leaked key valid for another 24 hours. If the leak is live, skip the overlap, set the new key alone, and take the logouts.

Budget about 30 minutes of hands-on work across two deploys, with a 24 hour wait before the cleanup.

## 1. Generate the new key, but do not install it yet

```
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

32 random bytes gives 256 bits, matching the SHA-256 output that HS256 is built on. Put it in your password manager or secret store for now.

## 2. Change the code to sign with one key and verify against a list

Deploy this with **no env change at all**. With `JWT_SECRET_ALT` unset the list has exactly one entry, so behavior is identical to today. That is what makes this deploy safe to ship by itself, and it is why it has to go first: every instance must be able to accept both keys before any instance starts signing with the new one.

New file, `src/auth/keys.js`:

```js
// JWT_SECRET signs new tokens. JWT_SECRET_ALT is accepted on verify only,
// and exists solely so a key rotation does not invalidate live tokens.
const signingKey = process.env.JWT_SECRET;
const altKey = process.env.JWT_SECRET_ALT;

if (!signingKey) throw new Error('JWT_SECRET is not set');

const verificationKeys = [signingKey, altKey].filter(Boolean);

module.exports = { signingKey, verificationKeys };
```

New file, `src/auth/verify.js`:

```js
const jwt = require('jsonwebtoken');
const { verificationKeys } = require('./keys');

function verifyToken(token) {
  let lastError;
  for (const [i, key] of verificationKeys.entries()) {
    try {
      const payload = jwt.verify(token, key, { algorithms: ['HS256'] });
      if (i > 0) console.warn('jwt: verified with JWT_SECRET_ALT');
      return payload;
    } catch (err) {
      // A valid signature that is expired or not yet valid means this key
      // matched, so report the real reason instead of trying the next key.
      if (err.name === 'TokenExpiredError' || err.name === 'NotBeforeError') throw err;
      lastError = err;
    }
  }
  throw lastError;
}

module.exports = { verifyToken };
```

At your signing call site:

```js
const { signingKey } = require('./auth/keys');
const token = jwt.sign(payload, signingKey, { algorithm: 'HS256', expiresIn: '24h' });
```

Four notes on that code. HS256 verification is a single HMAC, so trying two keys costs microseconds and you will not see it in latency. `algorithms: ['HS256']` pins the algorithm so a token cannot talk you into verifying it a different way; jsonwebtoken v9 already restricts a string secret to the HS family, so this is belt and braces there, but it matters if you are still on v8. `verifyToken` is synchronous and throws, matching `jwt.verify` without a callback; if your middleware uses the callback form instead, wrap the call in try/catch. Adapt `require`/`module.exports` to `import`/`export` if the project is ESM or TypeScript.

Expected result after this deploy: every existing session still works, and `jwt: verified with JWT_SECRET_ALT` never appears in the logs.

## 3. Switch the signing key

Set `JWT_SECRET` to the new value, add `JWT_SECRET_ALT` set to the old value, and restart. Node reads `.env` once at process start, so a restart is required; nothing picks this up live.

```
JWT_SECRET=<new key from step 1>
JWT_SECRET_ALT=<the old key>
```

If more than one process or container serves this API, split that into two restarts so no instance is ever asked to verify a key it does not have:

- 3a. Set `JWT_SECRET_ALT=<new key>` and leave `JWT_SECRET` on the old value. Roll every instance. Nothing changes for users; you are only pre-loading the new key.
- 3b. Set `JWT_SECRET=<new key>` and `JWT_SECRET_ALT=<old key>`. Roll every instance. Mid-rollout, some instances sign with the old key and some with the new, and every instance accepts both, so requests keep working either way.

Expected result: new logins get new-key tokens, and anyone already logged in stays logged in and starts producing `verified with JWT_SECRET_ALT` warnings.

## 4. Wait 25 hours

A token issued one second before the cutover expires 24 hours after it. The extra hour covers clock skew between servers and a rollout that took a while to finish. Count from the moment the last instance finished step 3, not from when you started it.

## 5. Delete the old key

Remove the `JWT_SECRET_ALT` line and restart. Then delete the old secret everywhere else it lives: your secret manager, CI variables, any `.env` on a developer machine, and any deploy config. A rotation only accomplishes something once the old value is actually gone.

The fallback code from step 2 stays. It is the mechanism, and next time you rotate you start at step 1 instead of rebuilding it.

## What I could not check

Your code is not available to me, so three things below are assumptions rather than verified facts.

1. I have not seen your repo. `src/auth/keys.js` and `src/auth/verify.js` are new files, but the sign and verify call sites are wherever your code touches them today. Find them with `grep -rn "jwt\.sign\|jwt\.verify\|JWT_SECRET" src/`.
2. I do not know what else uses `JWT_SECRET`. If refresh tokens, password reset links, email verification links, or `cookie-parser` signed cookies share it and outlive 24 hours, the wait in step 4 has to cover the longest of those lifetimes instead. Refresh tokens are the usual trap here, since a 30 day refresh token means a 30 day overlap.
3. I do not know your jsonwebtoken version or how many instances serve the API, which is why steps 2 and 3 each carry a branch.

After step 3, watch your logs for `verified with JWT_SECRET_ALT`. Once 25 hours pass with zero hits, step 5 is safe.
