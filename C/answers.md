# Task C — Xero Multi-Tenant API Integration Review

**Assumptions**

- Xero Accounting API (`/api.xro/2.0`), OAuth 2.0 Authorization Code + PKCE, confidential client, one app serving many tenant connections.
- "Latest SDK" (xero-node / xero-python / xero-java current release). Treat the SDK as a thin HTTP wrapper: it will happily retry, cache tokens, and swallow headers unless you configure it. Its retry and idempotency defaults need checking; most of the defects below come from them.
- Numbers quoted (token lifetimes, limits) are Xero's documented values at the time of writing; the *design* is what matters, and the limits must be read from config, not hard-coded.

---

## C1. Connection verification

### Minimum call sequence

| # | Call | Purpose |
|---|------|---------|
| 1 | `GET https://login.xero.com/identity/connect/authorize?response_type=code&client_id=…&redirect_uri=…&scope=openid profile email offline_access accounting.transactions accounting.settings&state=<nonce>&code_challenge=…&code_challenge_method=S256` | Starts consent; declares the exact scope set you will rely on |
| 2 | `GET /callback?code=…&state=…` | User consent result; `state` must equal the nonce you stored |
| 3 | `POST https://identity.xero.com/connect/token` (`grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`, client auth) | Exchanges the single-use code for `access_token` (~30 min), `refresh_token` (~60 days, rotating), `expires_in`, and the **actually granted** `scope` |
| 4 | `GET https://api.xero.com/connections` with `Authorization: Bearer <access_token>` | Enumerates the tenants this user authorised: `[{id, tenantId, tenantType, tenantName}]` |
| 5 | *(recommended smoke test)* `GET https://api.xero.com/api.xro/2.0/Organisation` with `xero-tenant-id: <tenantId>` | Proves the tenant header is accepted and an accounting read path works end-to-end |

Four calls are the true minimum (1–4); step 5 is the cheapest proof that steps 3 and 4 compose into a working tenant-scoped session.

### What each step actually proves

- **Step 1** proves only *intent*: your client ID is recognised for that redirect URI, and the scope string is syntactically acceptable. Nothing about the user or the tenant yet.
- **Step 2** proves *user consent was granted* and that the response was not injected — the `state` comparison is your CSRF/code-injection control. A missing/mismatched `state` must abort before step 3.
- **Step 3** proves *client authentication* (secret or PKCE verifier), that the code is valid, unexpired and bound to the same `redirect_uri`, and it tells you the **granted** scope — which can be narrower than requested. Always assert `granted ⊇ required`, never assume.
- **Step 4** is the de-facto token introspection and the **only** authoritative source of tenant selection. It proves the access token is live and accepted by the resource server, and returns exactly the orgs the user consented to. Xero has no `/me`-style endpoint that validates accounting access; `/connections` is it.
- **Step 5** proves the two-dimensional authorisation model: `token` × `xero-tenant-id`. A token can be valid while a tenant header is wrong — that is a 403/404, not a 401, and only step 5 distinguishes them.

For test design, note that tenant selection happens on the client side rather than inside the token. One token covers N tenants; switching tenant is a header change, not a re-auth. Therefore every tenant-scoped test needs a "same token, different tenant header" case.

### How I would test it

- Replay the authorisation `code` → second exchange must fail.
- Tamper `state`; drop `state`; replay an old `state` → abort before token exchange.
- Mismatch `redirect_uri` between step 1 and step 3 → rejected.
- Deny consent → `error=access_denied` handled as a user-facing state, not an exception.
- Request a scope, then check the granted scope string; simulate a user unticking a permission.
- Refresh-token rotation: use refresh token twice → `invalid_grant`; assert no retry storm (see C2).
- Remove the connection in Xero, then re-run step 4 → tenant disappears; cached tenant must be invalidated.

---

## C2. Failure diagnosis: 401 / 403 / 404

### Decision tree

```
401 Unauthorized  ("who are you?")
├─ Header missing/malformed, or stripped by a proxy/gateway/logging middleware
│    → assert the wire request, not the SDK object; check for double "Bearer Bearer"
├─ JWT exp in the past (decode payload for exp only; allow ≤60 s clock skew)
│    → refresh once → success? done
│         └─ refresh returns invalid_grant
│              ├─ refresh token idle > 60 days           → full re-consent
│              ├─ old refresh token reused after rotation → token-refresh stampede
│              │    (two workers refreshing concurrently) → single-flight the refresh
│              └─ user revoked app / connection removed   → full re-consent, mark tenant disconnected
├─ Token fresh, 401 on ONE tenant only → connection removed for that tenant
│    → GET /connections, diff against your tenant table, mark disconnected
└─ Token fresh, 401 on ALL tenants → environment/client mismatch
     (token minted by a different client_id or demo/staging app), clock skew, wrong identity host
```

```
403 Forbidden  ("I know you, you may not do this")
├─ Granted scope < required scope (e.g. accounting.transactions.read vs .write)
│    → compare token response `scope` against endpoint requirement; re-consent with incremental scope
├─ tenantId well-formed but not in /connections
│    → tenant misconfiguration or cross-tenant access attempt → security event, not a retry
└─ User's role in the org lacks the permission → surface as actionable 4xx; never retry
```

```
404 Not Found  ("that thing isn't here")
├─ Wrong path/version/base URL (api.xero.com vs identity host, /api.xro/2.0 missing, casing)
│    → config assertion at startup, not at runtime
├─ Resource GUID invalid, deleted, or VOIDED in that tenant → reconcile, do not retry
└─ Resource exists but belongs to another tenant → tenant-scoping bug (treat as P1 security defect)
```

### Triage rules I would enforce

1. **401 gets exactly one refresh attempt per request.** A refresh loop is an outage generator; cap it and alert.
2. **Never conflate 401 and 403 in code paths.** 401 = re-auth eligible; 403 = configuration/permission, permanently non-retryable.
3. **Disambiguate with `/connections`, not with guesses.** It is cheap, cached, and answers "is this tenant still mine?".
4. **Capture on every failure:** `Xero-Correlation-Id` response header, tenant ID, endpoint, HTTP status, Xero `ErrorNumber`/`Message`, attempt count, token `exp` (timestamp only — never the token).
5. **Environment configuration checklist** (the usual culprit behind "works in sandbox"): per-environment client ID/secret, per-environment tenant mapping table, correct hosts (`login.xero.com` / `identity.xero.com` / `api.xero.com`), proxy header stripping, NTP-synced clocks, sandbox vs demo company confusion.

**Tests:** inject a stale token (freeze the clock), a revoked connection, a scope downgrade, a tenant-ID swap between two connected orgs, and a base-URL override. Each must land in a distinct branch of the tree — if two causes produce the same log line, your tree is not testable.

---

## C3. Resumable incremental synchronisation for a large org

### Design

**Cursor record (per tenant × entity):**

```
sync_cursor(tenant_id, entity, run_id, run_started_at_utc,
            watermark_utc, page, last_committed_id, status, lease_owner, lease_expires_at)
```

**Run loop**

1. **Acquire a lease** for `(tenant, entity)` — single-flight. Two concurrent syncs of the same tenant is the #1 duplicate source.
2. **Window** = `[watermark − overlap, run_started_at − safety_lag]`, with `overlap` ≈ 5 min (late writes, clock skew) and `safety_lag` ≈ 2 min (avoid racing records committed mid-request).
3. **Page** with `page`/`pageSize` (invoices: 100/page) and, where supported, `If-Modified-Since` (UTC, second precision, inclusive).
4. **Per page:** fetch → transform → **upsert by natural key** (`InvoiceID`) → **commit data + page checkpoint in one transaction**. Checkpoint after commit, never before.
5. **On completion:** advance `watermark = run_started_at` — **not** `max(UpdatedDateUTC)`. Advancing to the max observed timestamp silently skips records written during the pass.
6. **On resume:** restart from `last_committed_id`/`page` of the same `run_id`. If the run is older than a staleness threshold, restart the run from the watermark instead — resuming a week-old page cursor is worse than redoing it.

### Guards

| Risk | Control |
|---|---|
| Duplicates | At-least-once delivery + idempotent upsert keyed on remote ID; per-run `seen_ids` set; DB unique constraint as the last line of defence |
| Partial failure | Page-level transactions; failed page does not advance the checkpoint; poison record quarantined and the run continues |
| Offset-pagination drift (records inserted mid-pass shift pages) | Never trust ordering; dedupe by ID; overlap window on the next run; tolerate skipped-then-recovered records |
| Out-of-order updates | Last-write-wins by `UpdatedDateUTC`, not by arrival order; compare before overwrite |
| Deletes / voids | They may not appear in a delta; run a periodic **ID reconciliation** (full key list vs local) |
| 429 / 5xx mid-run | Backoff inside the page loop (see C4); the checkpoint preserves progress |
| Watermark regression | Monotonic guard: `new_watermark = max(old, computed)` |

### Tests

Kill the process between page N and N+1 and assert zero duplicates and zero gaps; deliver the same page twice; update a record between page 1 and page 3; run two workers simultaneously (lease must reject one); force a 429 on page 2; empty tenant; a record whose `UpdatedDateUTC` equals the watermark exactly (inclusive-boundary bug); DST/timezone edges (everything in UTC).

---

## C4. Handling HTTP 429

### Read the response before you sleep

- `Retry-After` (seconds) — the authoritative wait.
- `X-Rate-Limit-Problem` — `minute` | `day` | `appminute` (per-tenant minute, per-tenant day, app-wide minute).

### Backoff

```
delay = max(Retry-After, min(cap, base × 2^attempt) × random(0.5…1.0)) + small jitter
base = 1 s, cap = 60 s
```

Full jitter is mandatory: a fleet of workers synchronised on the same 429 will re-collide.

**Different problem, different behaviour:**

- `minute` → sleep and retry; the request will succeed shortly.
- `appminute` → the whole app is over budget: pause **all** workers, not just this tenant's.
- `day` → do **not** retry in a loop. Park the tenant until the daily reset, mark the sync as deferred (not failed), alert, and let other tenants proceed. Burning retries against a daily cap is how you lose a day of sync.

### Retry budget

- Per request: max 5 attempts, ≤ 2 min wall clock (interactive); ≤ 15 min for batch.
- Per run: retries ≤ 10 % of total calls, else abort the run and requeue — a run where 30 % of calls are retries is a symptom, not a workload.
- Client-side pacing **below** the limit: token bucket at ~55 calls/min/tenant, burst 10; app-wide aggregator at ~9,000/min. Never discover the limit by hitting it.

### Do not retry

`400` (validation; the body will fail identically), `401` after the single allowed refresh, `403`, `404`, `405`, `409` (unless you have a documented optimistic-concurrency retry), `413` payload too large, `415`, `422`, `501`. Also: never retry a non-idempotent `POST` without an idempotency key — a retried invoice create is a duplicate invoice.

**Retry:** `429`, `500`, `502`, `503`, `504`, connection reset/timeout — and only with an idempotency key or a safe read.

---

## C5. Timeout on create — remote actually succeeded

### Prevention: make the retry safe by construction

1. **Idempotency-Key** — generate a UUIDv4 *per logical invoice*, persist it in the outbox row **before** the first send, and reuse it on every retry. Xero honours `Idempotency-Key` on write operations and retains the key for a bounded window (**24 h at the time of writing**); a replay returns the original result instead of creating a second invoice. Never regenerate the key on retry — that defeats the entire mechanism.
2. **Outbox state machine**, written locally, single source of truth:

   ```
   PENDING → IN_FLIGHT → CONFIRMED
                       → FAILED        (terminal, validated 4xx)
                       → UNKNOWN       (timeout / 5xx / connection reset)
   UNKNOWN → resolve by query → CONFIRMED | retry with same key → FAILED
   ```

   `UNKNOWN` is a first-class state. A timeout does not mean the request failed.
3. **Deterministic invoice number** (e.g. derived from your order ID) + Xero's per-tenant uniqueness on `InvoiceNumber`: a duplicate create is rejected, and you convert that rejection into a lookup-then-link. This is your safety net for retries beyond the idempotency window.
4. **Never delete** the outbox row; it is the audit trail for reconciliation.

### Detection: reconciliation

- **Query-before-create** for any `UNKNOWN` older than a threshold: `GET /Invoices?where=InvoiceNumber=="INV-123"` (or your `Reference`), then compare `Contact`, `Total`, `Date`, `LineItems`.
- **Daily three-way match:** local intent (outbox) ↔ remote object (by `InvoiceID` + `InvoiceNumber`) ↔ payment/allocation state. Output: matched, missing-remote, orphan-remote, amount-mismatch, duplicate-suspected.
- **Windowed sweep:** `If-Modified-Since` over the last 24–48 h to catch objects created by a retry whose response you never saw.
- **Hard check:** count of remote invoices per `InvoiceNumber` must never exceed 1; alert on any duplicate immediately (P1 — it is a financial-data defect, not a sync defect).

### Tests

Chaos proxy that forwards the request then drops the response; delay > client timeout with a 201 on the server; kill the worker after send, before commit; replay the same key 10× concurrently (exactly one invoice); let the key expire then retry (dedupe must fall back to invoice number); two workers picking the same outbox row (row lock must make one a no-op).

---

## C6. Observability and security

### Logs (structured JSON, one line per attempt)

`correlation_id` (propagated), `tenant_id` (opaque UUID, **not** the org name), `endpoint`, `method`, `status`, `duration_ms`, `attempt`, `retry_after`, `rate_limit_problem`, Xero `ErrorNumber`/`Type`, `xero-correlation-id`, `token_expiry` (timestamp only), `record_ids` affected (count + hashed IDs). Log at the **attempt** level, not just the request level — otherwise retries are invisible.

### Metrics

- Traffic/latency: requests by endpoint and tenant; p50/p95/p99; error rate split by class (401/403/404/429/5xx).
- Auth: refresh success/failure, re-consent events, auth-failure rate per tenant, token age at use.
- Limits: 429 rate, `Retry-After` distribution, consumption vs 60/min and 5,000/day per tenant, app-minute headroom.
- Sync: lag = `now − watermark`, records/min, pages/run, retry ratio, quarantined records, lease contention.
- Integrity: duplicates prevented (idempotent replays), reconciliation drift count, `UNKNOWN` outbox age.
- Reliability: circuit-breaker state, queue depth, worker heartbeat.

### Alerts

Auth-failure spike or any sustained 401 on a previously healthy tenant; refresh failure > N in 5 min (token-stampede signature); 429 sustained > 5 min or day-limit at 80 %; p95 latency breach; sync lag > 15 min or watermark unchanged for 2 cycles; **any** duplicate detected; any reconciliation mismatch; `UNKNOWN` older than 1 h; 5xx rate > 1 %.

### Never log

Access/refresh tokens, `Authorization` header, client secret, PKCE verifier, authorization code, cookies/session IDs, full request/response bodies (they contain contact PII, addresses, emails, tax IDs, bank details, line-item descriptions), payment instruments. Enforce with a redaction middleware **and** a CI test that greps captured log fixtures for token-shaped strings — policy without a test decays.

### Token storage

- Refresh tokens server-side only, encrypted at rest (KMS/envelope encryption, per-tenant data key), in a secrets manager or a dedicated encrypted column — never in code, repo, env files committed to VCS, client-side storage, or logs.
- Access tokens in memory only, short-lived, never persisted beyond the process.
- **Single-flight refresh** with a distributed lock: rotation invalidates the old refresh token, so concurrent refreshes cause `invalid_grant` cascades.
- Least-privilege IAM on the secret store, access audited, rotation procedure documented and tested; revoke tokens on tenant disconnect; key rotation supported without downtime.
- Data minimisation: store only what reconciliation needs; define retention for payload copies.

---

## References

- Xero OAuth 2.0 — Authorization Code flow: <https://developer.xero.com/documentation/guides/oauth2/auth-flow/>
- Xero OAuth 2.0 — Scopes: <https://developer.xero.com/documentation/guides/oauth2/scopes/>
- Xero API limits (60/min per tenant, 5,000/day per tenant, 10,000/min per app, `Retry-After`): <https://developer.xero.com/documentation/guides/oauth2/limits/>
- Xero — Idempotent requests: <https://developer.xero.com/documentation/best-practices/data-integrity/idempotency/>
- Xero Accounting API — Invoices (paging, `If-Modified-Since`): <https://developer.xero.com/documentation/api/accounting/invoices>
- Xero SDKs: <https://github.com/XeroAPI/xero-node> · <https://github.com/XeroAPI/xero-python>
