# OP-02 — Authentication, Sessions & Parental Consent

**Goal:** real parent accounts, real tokens, real ownership enforcement, and a consent
record that satisfies India's DPDP rules for children's data.
**Blocked by:** OP-01
**Touches:** `backend/` + `frontend/`

---

## 1. The problem

| Where | What's wrong |
|---|---|
| `backend/app/services/mock_auth.py` | Demo tokens, in-memory users |
| `frontend/services/auth.ts` | **Login cannot fail.** On error it returns `session_token: "local-session-<timestamp>"` and a fabricated user. |
| `frontend/services/session.ts` | Token in `sessionStorage` — readable by any XSS |
| `frontend/services/api.ts` | **No `Authorization` header exists.** The client holds a token it never sends. |
| everywhere | No refresh token, no rotation, no expiry handling, no logout |

The fabricated-session path is the worst of these. It means nobody has ever seen a real
authentication failure in this app, so no failure handling has ever been exercised.

---

## 2. Backend design

Fully specified in `../backend-architecture.md` Phase 2. The essentials:

| Concern | Decision |
|---|---|
| Password hashing | Argon2id (`argon2-cffi`) |
| Access token | JWT HS256, **15 minutes**, in the response body |
| Refresh token | **30 days**, hashed at rest, rotated on every use |
| Rotation | Old token revoked, replacement joins the same `family_id` |
| Theft detection | Presenting an already-revoked token **revokes the entire family** and returns 401 |
| Principal | Parents only. Children never authenticate. |
| Ownership | An `owned_child` dependency returns **404**, never 403 — 403 confirms the resource exists |
| Key rotation | A `kid` claim in the JWT so `SECRET_KEY` can rotate without logging everyone out |
| Rate limits | Login 5 / 15 min per email **and** 20 / 15 min per IP; register 3 / hour per IP |

---

## 3. The web-specific decision — do not skip this

The backend spec assumed a React Native client storing the refresh token in
Keychain/Keystore. **A browser has no equivalent.**

> The backend must set the refresh token as an
> **`HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`** cookie when the request carries
> `X-Client: web`, and read it from that cookie on `/refresh`. The access token stays in
> the JSON response body and lives in JavaScript memory only.

Without this, the only place to put a 30-day refresh token in a browser is `localStorage`,
which any XSS can read — undoing the entire authentication effort. CSRF is covered by
`SameSite=Lax` plus requiring a JSON content type on refresh.

This is additive and does not change any mobile contract. Decide it before the backend work
starts so it lands in one pass.

---

## 4. Web token handling

```
Access token   → module-scope variable + React context. Lost on reload, by design.
Refresh token  → HttpOnly cookie. Never visible to JavaScript.
On app load    → one /auth/refresh call; cookie present → session silently restored
On 401         → single-flight refresh, then replay the original request once
On refresh 401 → clear everything, route to login, show "please sign in again"
```

**Single-flight is mandatory.** Ten queries hitting a stale token must trigger **one**
refresh, not ten. Ten concurrent refreshes would trip the backend's rotation-reuse
detection and revoke the whole family — logging the parent out for behaviour that was
actually correct. This is the single easiest thing to get wrong here.

`frontend/services/session.ts` is deleted entirely.

---

## 5. Parental consent — DPDP Rule 10

India's Digital Personal Data Protection Rules were notified **14 November 2025**;
substantive obligations become enforceable **13 May 2027**. Rule 10 requires *verifiable*
consent from a parent or guardian before processing the data of **anyone under 18**, and
the Act prohibits behavioural tracking and targeted advertising directed at children.

| Requirement | Implementation |
|---|---|
| Verifiable consent | `consent_records` row required before any child profile can be created |
| Immutable trail | Append-only: who consented, when, for what purpose, how verified, policy version |
| Explicit action | Unticked checkbox **plus** a button. Never pre-ticked, never consent-by-continuing. |
| Placement | Behind the parent gate. Unreachable from the child surface. |
| Withdrawal | Visible in parent settings, with a working revocation path |
| No behavioural tracking | No ad SDK, no third-party analytics, anywhere in the codebase |

**This is engineering guidance, not legal advice. Have counsel review before launch.**

---

## 6. Acceptance criteria

**Backend**

- [ ] `mock_auth.py` deleted.
- [ ] Passwords stored as Argon2id; plaintext appears in no log, response, or column.
- [ ] Access token expires in 15 min; refresh in 30 days.
- [ ] Refresh rotates: old revoked, replacement in the same family.
- [ ] Reusing a revoked refresh token revokes the whole family and returns 401 — with a test.
- [ ] Logout revokes the presented token's entire family.
- [ ] Parent A requesting **any** of Parent B's children returns **404** — one test per child-scoped route, no exceptions.
- [ ] 6th login attempt for one email within 15 min returns 429 with `Retry-After`.
- [ ] Child creation is impossible without an active `consent_records` row.
- [ ] The refresh cookie is set with `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` for `X-Client: web`.
- [ ] Coverage on `auth_service.py` ≥ 90%.

**Web**

- [ ] `grep -rn "sessionStorage\|localStorage" frontend/` returns **zero** token results.
- [ ] The refresh cookie is not readable from JavaScript — verified in devtools.
- [ ] A page reload silently restores the session via one `/auth/refresh` call.
- [ ] **10 concurrent 401s trigger exactly one refresh** — tested with a request counter.
- [ ] A failed refresh clears state and routes to login **once** — no redirect loop.
- [ ] Login failure shows a real error. The `local-session-${Date.now()}` path is gone — tested.
- [ ] Consent screen blocks first child creation and sits behind the parent gate.
- [ ] Consent record and a withdrawal path are visible in parent settings.
- [ ] Logout clears memory, cookie, and the entire React Query cache.

---

## 7. Prompt

> OP-01 is complete, so PostgreSQL and the `users` / `refresh_tokens` / `children` /
> `consent_records` tables exist. Read `docs/backend-architecture.md` Phase 2 §7,
> `docs/frontend-architecture.md` §3.1 §3.2 §0.5, and `docs/ops/OP-02-authentication.md`.
> Implement real authentication end to end.
>
> **Backend:** Argon2id password hashing; 15-minute access tokens carrying a `kid` claim so
> the signing key can rotate; 30-day refresh tokens hashed at rest and rotated on every use,
> where the old token is revoked and the replacement joins the same `family_id`; and
> reuse-detection where presenting an already-revoked refresh token revokes the entire family
> and returns 401. When a request carries `X-Client: web`, return the refresh token as an
> `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` cookie instead of in the JSON body, and
> read it from that cookie on `/refresh`; the access token stays in the body. Implement
> `current_parent` and `owned_child` dependencies where `owned_child` returns **404**, never
> 403, for another parent's child. Add the login and register rate limits. Block child
> creation unless an active `consent_records` row exists. Delete `mock_auth.py`.
>
> **Web:** hold the access token in memory only — delete `services/session.ts` and every
> token reference to `sessionStorage`. Restore the session on load with a single
> `/api/v1/auth/refresh` call. Implement a **single-flight** refresh interceptor so N
> concurrent 401s produce exactly one refresh call before replaying the original requests
> once; a failed refresh clears state and routes to login without looping. **Delete the
> fabricated-session fallbacks in `services/auth.ts`** — a failed login must surface a real
> error, never `local-session-${Date.now()}`. Build the parental consent flow behind the
> parent gate: plain language about what is and is not collected, an unticked checkbox plus
> an explicit button, posting the policy version to the consent endpoint, with the record and
> a working withdrawal path in parent settings.
>
> Prove: zero token references to browser storage; the refresh cookie unreadable from JS; 10
> concurrent 401s producing exactly one refresh; login failure producing an error rather than
> a session; a cross-parent 404 test for every child-scoped route; and child creation blocked
> without consent.
