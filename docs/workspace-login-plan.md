# Private workspaces and sign-in

Use managed OpenID Connect sign-in and keep FastAPI responsible for workspace access. Start with one identity provider and a private workspace library that restores the user's sources, checks, conversations and brief across devices. Treat sharing and team roles as a later product decision.

Today FastAPI lists workspaces from one JSON store. The browser caches recent workspace metadata, and the Next.js proxy forwards calls without an account identity. A sign-in screen alone would leave those API operations shared.

1. Add a server-side session through the Next.js app. Use an established OIDC library with authorization code and PKCE, state and nonce validation, and a secure HttpOnly session cookie. Map verified issuer and subject to an internal user ID. Require the proxy to authenticate workspace requests, validate origins on writes and forward a short-lived signed internal identity. FastAPI verifies that identity and rejects unauthenticated workspace access, including direct requests.
2. Move hosted workspace data to PostgreSQL. Keep the existing response models and API routes. Add a required owner ID and an owner index to workspaces. Scope child records and writes through their parent workspace. Preserve source revisions, answer history links and saved-brief references. Use transactions for refresh, answer saves and migration. Return 404 for workspace IDs outside the caller's account.
3. Add sign-in and sign-out to the header and show the account's workspace library after sign-in. Clear client workspace state on account change and load the library from the server. Scope any retained recent-workspace cache to the signed-in account. Keep a separate public demo using curated fixtures if desired.
4. Back up the existing JSON and import it with a server-side operator command that requires an explicit target account. Preserve IDs and verify counts and relationships in a dry run before the transactional import. Repeat imports must be safe. Browser cache entries are hints for navigation and cannot establish ownership.
5. Gate rollout on two-account tests that exercise list, direct links, source inspection, refresh, review updates, Ask, follow-ups and Brief. Include expired sessions, sign-out, cross-account ID substitution and a browser session switching accounts. Apply per-user request limits while keeping the global inference cap. Test backup restoration before switching hosted traffic.

The first implementation slice is sign-in, owner-scoped create/list/reopen and cross-account tests. Then migrate the remaining workspace operations behind the same authorization boundary before opening hosted access. Provider selection depends on the deployment environment and its account requirements.

References

- [OpenID Connect Core, claim stability and uniqueness](https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability)
