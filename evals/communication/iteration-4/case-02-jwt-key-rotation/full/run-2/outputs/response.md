Three deploys, in this order: make the API verify against both secrets, then switch signing to the new one, then drop the old one once the last token signed with it has expired. Keeping the old secret in the verify list for one full token lifetime is what stops anyone from being logged out. Budget about 30 minutes of work across steps 1 to 4, then a 24 hour wait before step 5.

If you are rotating because the old secret leaked, this plan is the wrong one: it keeps the leaked key valid for another 24 hours, so anyone holding it can keep minting tokens that whole time. For a leak, do it in one deploy, set the new secret alone, and accept that everyone signs in again.

## The rotation

1. Find everything that verifies these tokens: `grep -rn "JWT_SECRET" . --exclude-dir=node_modules`. Every process that calls `jwt.verify` needs the step 3 change before step 4 lands, including a second service or an API gateway if one checks the same tokens.

2. Generate the new secret and keep the old value somewhere you can paste it. `node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"` gives 32 random bytes, the minimum key size HS256 is built for. Do not overwrite `JWT_SECRET` yet.

3. Replace your sign and verify calls with a small keyring: the first secret in the list signs, every secret in the list verifies. Then set `JWT_SECRETS=<old>,<new>` in `.env` and in wherever your production env vars actually live (host dashboard, secret manager), and deploy. Nothing changes for users on this deploy; tokens are still signed with the old key.

```js
// e.g. src/jwt.js (I have not seen your code, so this is probably not your path)
const jwt = require('jsonwebtoken'); // import jwt from 'jsonwebtoken' if you are on ESM or TypeScript

// First entry signs. Every entry verifies.
const SECRETS = (process.env.JWT_SECRETS || process.env.JWT_SECRET || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

if (SECRETS.length === 0) throw new Error('JWT_SECRETS is not set');

function signToken(payload) {
  return jwt.sign(payload, SECRETS[0], { algorithm: 'HS256', expiresIn: '24h' });
}

function verifyToken(token) {
  let lastError;
  for (const secret of SECRETS) {
    try {
      return jwt.verify(token, secret, { algorithms: ['HS256'] });
    } catch (err) {
      // A bad signature means "wrong key, try the next one".
      // Expired or malformed is final; no other key changes that answer.
      if (err.name !== 'JsonWebTokenError') throw err;
      lastError = err;
    }
  }
  throw lastError;
}

module.exports = { signToken, verifyToken };
```

Keep every option you already pass to `jwt.sign` and `jwt.verify` (`issuer`, `audience`, `subject`, `clockTolerance`); the key is the only thing changing. The fallback to `JWT_SECRET` keeps this deploy working on any machine the new variable does not reach. Pinning `algorithms: ['HS256']` stops a token from being accepted under some other algorithm. If your current secret contains a comma, split on a character it does not contain.

4. Swap the order to `JWT_SECRETS=<new>,<old>` and redeploy. No code change. From this moment every token issued is signed with the new key, and the tokens already out there, up to 24 hours' worth, keep verifying against the old one. A rolling restart is safe here because instances on both the old and the new env hold both secrets.

5. At least 24 hours after step 4 has finished rolling out, set `JWT_SECRETS=<new>`, redeploy, and delete the old secret from your secret store. Add an hour of margin for clock skew. If refresh tokens are signed with the same secret and live longer than 24 hours, wait out the longest of those instead; the old key has to outlive the longest-lived token that was ever signed with it.

## What I could not check

I do not have your code. I am assuming one place calls `jwt.sign` and one middleware calls `jwt.verify`; if signing is spread across several route files, step 3 is a bigger edit than 30 minutes and the grep in step 1 will show you how much bigger. I also cannot tell whether anything outside this API verifies these tokens, or whether refresh tokens share `JWT_SECRET`, which is why steps 1 and 5 ask you to look.

After step 4 deploys, call a protected endpoint twice: once with a token minted before the change, once with a fresh one. Both should return 200. If the older token gets a 401, that machine's `JWT_SECRETS` lost its second entry.
