# 02 · Backend Architecture — `api-service`

> Scope: `backend/api-service` — the business-state service. Everything a user
> logs into, everything with a permission attached, and the only client of
> `ai-service`.
>
> **Status: scaffold.** §1 lists exactly what exists today. Everything from §3
> onward is design, and is marked _Planned_. Nothing here should be read as
> working code.

---

## 1. What exists today

```
backend/api-service/
├── alembic/                 configured, zero migrations (versions/ is empty)
├── alembic.ini
├── app/
│   ├── core/config.py       Settings — incl. secret_key, algorithm,
│   │                        access_token_expire_minutes, ai_service_url
│   ├── core/logging.py
│   ├── db/base.py           DeclarativeBase
│   ├── db/session.py        async engine + AsyncSessionLocal + get_db
│   ├── models/user.py       users table — id, email, hashed_password,
│   │                        full_name, is_active, created_at
│   ├── schemas/user.py      UserCreate · UserRead
│   ├── services/ai_client.py  AIServiceClient — health() and infer()
│   ├── api/routes/health.py
│   ├── api/routes/users.py  CRUD against an in-memory dict
│   ├── api/routes/ai.py     POST /api/v1/ai/infer — proxy
│   └── main.py              FastAPI app, CORS, routers
└── tests/                   3 tests
```

Three things about this scaffold are worth knowing before extending it.

**`users.py` does not touch the database.** It reads and writes
`_users: dict[uuid.UUID, UserRead]`, a module-level dict. The `User` ORM model
exists and is never used by a route. Data vanishes on restart.

**`ai_client.infer()` calls an endpoint that no longer exists.** It POSTs to
`/api/v1/inference/predict`, which was the generic-inference route on
`ai-service`. That route was deleted when the ML pipeline replaced it. The call
returns 404 today. Rewiring it is the first task in §11.

**No migration has ever been generated.** Alembic is configured, `versions/` is
empty, and `create_all` is not called either — so the `users` table does not
exist in any database.

`secret_key`, `algorithm` and `access_token_expire_minutes` are present in
`Settings` and unused. No authentication code has been written.

---

## 2. Responsibilities

| Owns                                             | Delegates                         |
| ------------------------------------------------ | --------------------------------- |
| Authentication, sessions, tokens                 | —                                 |
| Roles and permissions (RBAC)                     | —                                 |
| CPSE isolation — who may see whose materials     | —                                 |
| Upload: file receipt, validation, batch tracking | Standardization → `ai-service`    |
| Review workflow and its state machine            | The verdict itself → `ai-service` |
| National material code issuance                  | —                                 |
| Legacy-code mapping, preserved forever           | —                                 |
| Exports and reporting                            | Matching → `ai-service`           |
| Business audit trail                             | Pipeline audit → `ai-service`     |

**`api-service` must never contain matching logic.** No thresholds, no rules, no
scoring. If a question is "are these two materials the same?", it is an
`ai-service` question. If it is "may this user see this material, and what
happens when they approve it?", it is an `api-service` question.

> 💡 **Implementation Note**: `ai-service` provides native support for review workflows, queues, and national code mapping via HTTP (see [**`docs/AI_SERVICE_API_SPECIFICATION.md`**](AI_SERVICE_API_SPECIFICATION.md)). `ai-service` has no user model — no roles, no caller identity, no authorisation — so `api-service` must do all of that before proxying, and may pass an `actor` label in the request body for the audit trail.

---

## 3. Layers · _Planned_

Same shape as `ai-service`, with a repository layer added because this service
has genuine multi-tenant query concerns that benefit from being centralised.

```
app/routes/           HTTP. Auth dependencies attach here.
        ↓
app/schemas/          Pydantic DTOs
        ↓
app/services/         Business orchestration. Owns the transaction.
        ↓
app/repositories/     Queries. Every query is CPSE-scoped by construction.
        ↓
app/models/           SQLAlchemy tables

app/config.py         Settings (.env) + logging
app/database.py       Engine, session, Base
app/auth.py           JWT, RBAC, the security context
```

The one addition over `ai-service` is `app/repositories/`; everything else is
the same four-layer stack, so a developer moving between the two services does
not have to relearn where anything lives.

The repository layer exists for one reason: **CPSE isolation must not be
something a route remembers to do.** A repository method takes the caller's
scope as a required argument, so an unscoped query is a type error rather than a
data leak.

```python
# app/repositories/materials.py                                  Planned
async def list_for(session, scope: AccessScope, **filters) -> list[Material]:
    stmt = select(Material)
    if not scope.is_national:
        stmt = stmt.where(Material.cpse_id == scope.cpse_id)
    ...
```

---

## 4. Users, roles and CPSE isolation · _Planned_

### Roles

| Role                | Scope     | May                                                           |
| ------------------- | --------- | ------------------------------------------------------------- |
| `CPSE_UPLOADER`     | Own CPSE  | Upload extracts, view own materials and quality flags         |
| `CPSE_REVIEWER`     | Own CPSE  | Everything above, plus decide review tasks touching own CPSE  |
| `CPSE_ADMIN`        | Own CPSE  | Everything above, plus manage own CPSE's users                |
| `NATIONAL_REVIEWER` | All CPSEs | Decide cross-CPSE review tasks, issue national codes          |
| `NATIONAL_ADMIN`    | All CPSEs | Everything, plus manage CPSEs, roles and domain configuration |
| `VIEWER`            | Own CPSE  | Read-only                                                     |

Two axes, kept separate: **what** a user may do (role) and **whose data** they
may do it to (scope). A `CPSE_REVIEWER` at NTPC and one at IOCL have identical
permissions and disjoint data.

### The cross-CPSE problem

A duplicate found between an NTPC material and an IOCL material belongs to
neither CPSE alone. A `CPSE_REVIEWER` sees such a pair — they cannot standardize
national inventory without seeing the other side — but:

- They see the other CPSE's **description and attributes**, because that is the
  evidence.
- They do **not** see its price, quantity or vendor.
- Their approval alone does not merge anything. A cross-CPSE merge needs a
  `NATIONAL_REVIEWER`, or a reviewer from each side.

That last rule is why `review_task` carries a `required_approvals` count rather
than a single decision column.

### Authentication

JWT bearer tokens, HS256, `secret_key` from settings, 24-hour expiry — all
already present as configuration. `argon2` or `bcrypt` for password hashing;
`hashed_password` on the existing `User` model expects it.

```python
# app/auth.py                                                    Planned
def create_access_token(subject: str, scope: AccessScope) -> str: ...
async def current_user(token: str = Depends(oauth2_scheme)) -> User: ...
def require(*roles: Role) -> Callable: ...       # FastAPI dependency
```

Every route carries `Depends(require(...))` explicitly. There is no
"authenticated by default" middleware, because a route that forgets to opt in
should fail closed and visibly, not silently serve everyone.

---

## 5. Data model · _Planned_

`ai-service` owns material data ([03 Part C](03_ML_ARCHITECTURE.md)).
`api-service` owns everything about people, process and identity.

```
cpse
 ├── 1:N  user
 └── 1:N  upload_batch
              └── 1:N  upload_row          (staging, pre-standardization)

review_task
 ├── N:1   references a match_result in ai-service (by id, no FK)
 └── 1:N   review_decision

national_code
 └── 1:N   code_mapping                    (legacy code → national code)

audit_event   (append-only)
```

| Table             | Holds                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `cpse`            | `id`, `code` (`NTPC`), `name`, `is_active`                                                                                                  |
| `user`            | Existing model plus `cpse_id`, `role`, `last_login_at`                                                                                      |
| `upload_batch`    | `id`, `cpse_id`, `uploaded_by`, `filename`, `sha256`, `row_count`, `status`, `received_at`                                                  |
| `upload_row`      | `batch_id`, `row_number`, the raw columns verbatim, `validation_errors`                                                                     |
| `review_task`     | `id`, `match_result_id`, `left_material_id`, `right_material_id`, `relationship`, `state`, `required_approvals`, `assigned_to`, `opened_at` |
| `review_decision` | `task_id`, `user_id`, `decision`, `comment`, `decided_at`                                                                                   |
| `national_code`   | `id`, `code` (`NUMM-BEARING-000001`), `category`, `canonical_description`, `issued_by`, `issued_at`, `superseded_by`                        |
| `code_mapping`    | `national_code_id`, `cpse_id`, `legacy_code`, `material_id`, `linked_at`, `unlinked_at`                                                     |
| `audit_event`     | `actor_id`, `action`, `entity_type`, `entity_id`, `before`, `after`, `occurred_at`                                                          |

### Two invariants this service must hold

**A legacy code is never overwritten, replaced or deleted.** `code_mapping` is
additive: issuing a national code _adds_ a row linking the CPSE's existing code
to it. Every CPSE keeps querying its own master by its own code forever. A
mapping that turns out to be wrong is closed with `unlinked_at`, not deleted.

**`sha256` on `upload_batch` makes re-uploads detectable.** The same file
submitted twice is a common procurement accident. Storing the digest lets the
service say "this is batch 41 again" instead of silently duplicating 400 rows.

### Cross-service references

`review_task.match_result_id` points at a row in `ai-service`'s database. There
is no foreign key — different service, possibly different database. The
consequence is stated plainly: a match result deleted by a re-run leaves an
orphaned task. `POST /materials/match-all` clears `match_result`, so
`api-service` must either re-resolve open tasks after a run or pin the evidence
it needs (`relationship`, `reason`, the attribute lists) onto the task at
creation time. **Pinning is the right answer** — a review task should hold the
evidence the reviewer was shown, not a pointer to evidence that can change
underneath them.

---

## 6. Upload · _Planned_

```
POST /api/v1/uploads   multipart CSV or XLSX
  │
  ├─ authenticate, require CPSE_UPLOADER
  ├─ size / MIME / extension check
  ├─ sha256 → duplicate-batch check
  ├─ parse headers → the eight required columns
  │     missing column ⇒ 422, nothing stored, error names the columns
  ├─ INSERT upload_batch (status = RECEIVED)
  ├─ INSERT upload_row per line, raw values verbatim
  └─ 202 Accepted { batch_id }
        │
        ▼
   background: POST ai-service /api/v1/materials/ingest
        │
        ├─ success ⇒ status = STANDARDIZED, quality summary attached
        └─ failure ⇒ status = FAILED, error stored, rows retained
```

`upload_row` stores the raw line **before** anything is validated or
standardized. If ingestion fails, the CPSE's data is still on the server and the
upload does not have to be repeated. This is the same invariant as
[03 §12 I1](03_ML_ARCHITECTURE.md), one layer earlier.

`ai-service` currently reads its dataset from a configured **file path**, not
from an upload. Wiring these together needs one of:

- `api-service` writes the batch to a path `ai-service` reads (simplest; keeps
  the current `ai-service` contract unchanged), or
- `ai-service` grows `POST /materials/ingest` with a request body carrying rows.

The first is the smaller change and is the recommended starting point.

---

## 7. The review workflow · _Planned_

```
                    ai-service returns a verdict
                              │
              ┌───────────────┼────────────────┐
              ▼               ▼                ▼
      EXACT_DUPLICATE   NEAR_DUPLICATE   FUNCTIONALLY_EQUIVALENT
       + PASS rules      or REVIEW        (always reviewed)
              │               │                │
              ▼               ▼                ▼
        AUTO_APPROVABLE    OPEN ─────────────► OPEN
              │               │
              │               ├─ approve ─► APPROVED
              │               ├─ reject ──► REJECTED
              │               └─ need info► NEEDS_INFO ──► OPEN
              ▼               │
           APPROVED ◄─────────┘
              │
              ▼
     national code issued / existing code linked
```

| State        | Meaning                                             |
| ------------ | --------------------------------------------------- |
| `OPEN`       | Awaiting a decision                                 |
| `NEEDS_INFO` | A reviewer asked the originating CPSE a question    |
| `APPROVED`   | Enough approvals recorded; ready for code issuance  |
| `REJECTED`   | Not the same article                                |
| `SUPERSEDED` | A re-run produced a different verdict for this pair |

**Auto-approval is a policy, not a default.** A pair may be auto-approved only
when _all_ of these hold, and the policy is stored so an auditor can see what it
was at the time:

- `relationship_type == EXACT_DUPLICATE`
- `hard_rule_status == PASS`
- no `conflicting_attributes`, no `missing_attributes`
- `confidence_kind == "heuristic_confidence"` **and** the deployment has enabled
  auto-approval for heuristic scores

That last condition exists because the score is not calibrated
([04 §5](04_RETRIEVAL_AND_MATCHER_INTERFACE.md)). Until a domain expert has
reviewed the gold labels, the honest default is **auto-approval off** — every
pair gets a human. Turning it on is a decision someone signs for.

---

## 8. National code issuance · _Planned_

```
NUMM-BEARING-000001
└┬─┘ └──┬──┘ └──┬──┘
 │      │       └─ zero-padded sequence within the category
 │      └───────── category from ai-service classification
 └──────────────── fixed prefix
```

On approval of a group:

1. If any member already carries a national code, **link to it**. Never issue a
   second code for the same article.
2. Otherwise issue the next sequence in the category, taking a row lock so two
   concurrent approvals cannot claim the same number.
3. Write one `code_mapping` row per member — `(national_code, cpse, legacy_code,
material_id)`.
4. Write an `audit_event` naming the actor, the task and every code linked.

A code is never reissued or renumbered. A merge that proves wrong is corrected by
setting `unlinked_at` on the mapping and issuing a new code, leaving the history
intact.

Clustering ([05 §8](05_MATCHING_AND_RULE_ENGINE.md)) suggests groups; it does not
create them. Transitivity is not guaranteed, so a cluster is a review grouping
and a human decides its membership.

---

## 9. Calling `ai-service` · _Planned_

`AIServiceClient` exists and needs rewriting against the real contract
([06 Part B](06_API_SPECIFICATION.md)):

```python
class AIServiceClient:                                         # Planned
    async def health(self) -> dict: ...
    async def ingest(self) -> IngestResult: ...
    async def matches_for(self, material_id: str, top_k: int = 10) -> MatchResult: ...
    async def match_all(self) -> MatchRunResult: ...
    async def quality_summary(self) -> QualitySummary: ...
    async def evaluation_report(self) -> EvaluationReport: ...
```

Rules for this boundary:

- **One client, one place.** No route calls `ai-service` directly.
- **Map failures at the boundary.** A connection error becomes `502`, not a
  traceback. The existing `ai.py` already does this correctly.
- **Never re-derive a verdict.** `api-service` stores what `ai-service` returned
  and shows it. It does not recompute, re-threshold or re-rank.
- **Carry the caveats through.** `confidence_kind`, the `note` on match
  responses and the `caveat` on evaluation reports reach the UI unaltered. They
  exist so nobody mistakes a heuristic for a probability, and stripping them at
  this layer would defeat that.
- **Long calls are jobs.** `match-all` takes seconds today and will take minutes
  at scale. It belongs behind `202 Accepted` + a job row, not a synchronous
  request.

---

## 10. Audit · _Planned_

Two audit trails, deliberately not merged:

|         | `ai-service.audit_log`             | `api-service.audit_event`                 |
| ------- | ---------------------------------- | ----------------------------------------- |
| Records | Pipeline runs, matching runs       | Logins, uploads, decisions, code issuance |
| Actor   | `system`, or a passed-through name | An authenticated `user_id`                |
| Answers | "What did the pipeline do?"        | "Who did what, and when?"                 |

They stay separate because they are trusted differently. `ai-service` cannot
authenticate anyone, so an actor name it records is a claim. `api-service` knows
who was holding the token.

`audit_event` stores `before` and `after` JSON for state changes, which is what
makes "why does this material carry this national code?" answerable a year later.

---

## 11. Implementation order

The dependency chain, shortest useful increment first:

1. **Make persistence real.** Alembic migration for `users`; rewire `users.py`
   off the module-level dict onto the session.
2. **Fix the dead call.** `ai_client.infer()` points at a deleted endpoint —
   replace it with the real `ai-service` methods from §9.
3. **`cpse` table and `user.cpse_id` + `user.role`.** Everything else depends on
   scope existing.
4. **Auth.** Password hashing, `/auth/login`, `current_user`, `require(...)`.
5. **`AccessScope` and the repository layer.** Isolation must land before any
   endpoint returns material data.
6. **Upload.** `upload_batch`, `upload_row`, the ingest handoff.
7. **Review tasks.** Task creation from match results, with the evidence pinned.
8. **National codes.** Issuance, mapping, the append-only guarantee.
9. **Exports and reporting.**

Steps 1–2 are corrections to existing code and are small. Step 5 is the one that
must not be deferred: adding isolation after routes exist means auditing every
route, whereas building it into the repository layer first makes an unscoped
query impossible to write by accident.

---

## 12. Things this document is not claiming

- No authentication, authorization, upload, review or code issuance exists today.
- The tables in §5 have not been created; no migration has been generated.
- `users.py` is in-memory and loses data on restart.
- `ai_client.infer()` is broken against the current `ai-service`.
- The auto-approval policy in §7 is a proposal. The honest default is off.

---

**Next:** [03 · ML Architecture — `ai-service`](03_ML_ARCHITECTURE.md)
