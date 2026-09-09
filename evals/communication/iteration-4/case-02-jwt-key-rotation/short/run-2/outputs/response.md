You can do this because signing and verifying do not have to use the same key. Add the new secret to the verifier first, keep accepting the old one for longer than any token signed with it can live, then delete the old one. Nobody gets logged out, because every token still in circulation verifies against a key the server is still holding.

One thing to settle before you start: if you are rotating because the old secret leaked, this procedure is the wrong one. It deliberately keeps the compromised key valid for another day. In a breach you swap the key in a single step, accept that everyone is logged out, and treat that as the point. Everything below assumes a scheduled rotation.

**1. Find everything the old secret signs**

```bash
grep -rn "JWT_SECRET\|jwt\.sign\|jwt\.verify" --include="*.js" --include="*.ts" .
```

You are looking for two things. First, any other service or worker that verifies these tokens; each one needs the new key deployed before you start signing with it. Second, anything besides access tokens signed with `JWT_SECRET`: refresh tokens, password reset links, email verification links, signed webhook payloads.

That second one sets the schedule. The wait in step 6 is governed by the longest-lived thing signed with the old key, not by the 24h access token. If reset links share the secret and are good for 7 days, the old key stays accepted for 7 days.

**2. Generate the new key**

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"
```

32 bytes is 256 bits, which matches what HS256 actually uses. Add it to `.env` and leave your existing `JWT_SECRET` line completely untouched:

```
JWT_SECRET=<unchanged>
JWT_SECRET_V2=<the new value>
JWT_ACTIVE_KID=v1
```

Note the `v1`. This deploy does not switch the signing key yet. Leaving `JWT_SECRET` alone matters more than it looks: renaming it now means every environment that still reads the old name breaks the moment it restarts.

**3. Make the code key-aware**

`kid` (key ID) is a standard JWT header field naming which key signed the token. Putting it in the header lets the verifier look up one key instead of guessing between two.

```js
// src/auth/jwt.js
const jwt = require('jsonwebtoken');

const LEGACY_KID = 'v1'; // tokens minted before this deploy carry no kid header

const keys = Object.fromEntries(
  Object.entries({
    v1: process.env.JWT_SECRET,
    v2: process.env.JWT_SECRET_V2,
  }).filter(([, secret]) => secret)
);

const activeKid = process.env.JWT_ACTIVE_KID;
if (!keys[activeKid]) {
  throw new Error(`JWT_ACTIVE_KID="${activeKid}" has no matching secret in the environment`);
}
console.log(`[jwt] keys loaded: ${Object.keys(keys).join(',')} | signing with: ${activeKid}`);

function signToken(payload) {
  return jwt.sign(payload, keys[activeKid], {
    algorithm: 'HS256',
    expiresIn: '24h',
    keyid: activeKid, // jsonwebtoken writes this to the "kid" header
  });
}

function verifyToken(token) {
  const decoded = jwt.decode(token, { complete: true });
  if (!decoded) throw new jwt.JsonWebTokenError('malformed token');

  const kid = decoded.header.kid || LEGACY_KID;
  const secret = keys[kid];
  if (!secret) throw new jwt.JsonWebTokenError(`unknown key id "${kid}"`);

  const claims = jwt.verify(token, secret, { algorithms: ['HS256'] });
  console.log(`[jwt] verified kid=${kid}`); // drop to debug level after step 7
  return claims;
}

module.exports = { signToken, verifyToken };
```

Four things in there are load-bearing:

Reading the header before verifying looks unsafe but is not. `kid` only chooses which key you try. A forged `kid` either names a key you already hold, in which case the signature check still fails, or names one you do not hold, in which case you reject outright. The signature is never skipped. The explicit `if (!secret)` guard is what keeps a bogus `kid` from reaching `jwt.verify` with `undefined` as the secret.

`algorithms: ['HS256']` is pinned on purpose. Recent jsonwebtoken versions already restrict a string secret to the HS family, so this is belt and braces rather than a fix for an open hole, but it costs one line and survives a package upgrade.

`jwt.JsonWebTokenError` is thrown rather than a plain `Error` so that existing middleware doing `err instanceof jwt.JsonWebTokenError` keeps behaving the same way.

If you would rather not decode first, jsonwebtoken also accepts a function in place of the secret, but only in its callback form: `jwt.verify(token, (header, cb) => cb(null, keys[header.kid]), { algorithms: ['HS256'] }, (err, claims) => { ... })`. Same result; the synchronous version above usually drops into existing middleware with less surgery.

Three tests are worth writing before this ships: a token signed with `v1` verifies (that is the whole "nobody gets logged out" guarantee), a token signed with `v2` verifies, and a token carrying `kid: v3` is rejected instead of crashing.

**4. Deploy this, and confirm every instance took both keys**

Roll it out, then check that the boot line reads `keys loaded: v1,v2` on every instance. If one instance is missing `JWT_SECRET_V2`, stop and fix that before going further. That instance would reject every new token the moment you flip.

Why this is a separate deploy from step 5: during a rolling update, an already-updated instance signs a `v2` token, the next request from that user lands on an instance that has never heard of `v2`, and they get a 401. That is the mass logout you are trying to avoid, arriving through the back door. If you run exactly one process and restart it atomically (a single Cloud Run revision, one `pm2 restart`), no two versions are ever live at once and you can merge steps 4 and 5. Keep them split for anything with replicas, rolling deploys, or blue/green.

**5. Flip the signing key**

Set `JWT_ACTIVE_KID=v2` and restart. No code change. Environment is read at process start, so editing the value alone does nothing until the process comes back. New logins now get `v2` tokens, and the up-to-24h of `v1` tokens already in the wild keep working.

**6. Wait out the longest lifetime from step 1**

For 24h tokens, wait 26 to 30 hours. The extra hours cover clock skew between machines and tokens minted in the final seconds before the flip. Meanwhile watch the `verified kid=` log line until `v1` stops appearing entirely. That count hitting zero, not the clock, is the real signal. If `v1` traffic is still non-trivial when you expected it gone, something is issuing or storing tokens you did not find in step 1, and you should go back rather than push ahead.

**7. Retire the old key**

Delete the `JWT_SECRET` line and restart. The filter drops `v1` from the map with no code change, and the `LEGACY_KID` fallback goes inert by itself, since a token with no `kid` now resolves to a key that is not there and gets rejected, which is correct at that point.

Then remove the old value everywhere else it lives: your secret manager, CI variables, teammates' local `.env` files, and any backup or snapshot of the file. Treat it as burned rather than recycling it as a future `v3`.

**What I could not check**

I have not seen your code, so take these as things to verify rather than facts:

- Whether anything besides access tokens is signed with `JWT_SECRET`. This is the single most common way a clean rotation turns into an incident, which is why it is step 1 and why it, not the 24h expiry, sets the length of the wait.
- Whether a second service, background worker, or websocket handler verifies these tokens. If so, it needs `JWT_SECRET_V2` and the same key map deployed before step 5, not after.
- Your `jsonwebtoken` major version. `keyid`, `decode(..., { complete: true })`, and the `JsonWebTokenError` export are stable across v8 and v9, but v9 changed verification defaults. Run `npm ls jsonwebtoken` and keep the pinned `algorithms` either way.
- How production actually gets its environment. If it uses platform env vars rather than a `.env` file loaded by dotenv, steps 2, 5, and 7 are changes in that platform's config, and "restart" means whatever that platform does to pick them up.

The snippet is written against your description, not run against your app.

Start with the grep in step 1. Whatever it turns up is what decides how long you wait in step 6.
