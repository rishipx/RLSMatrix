# Writing test suites

- [Suite format](#suite-format)
- [Actors](#actors)
- [Probes](#probes)
- [Pitfall: `RETURNING`](#pitfall-returning-on-a-probe-that-expects-an-rls-error)
- [Bundled examples](#bundled-examples)

## Suite format

A suite is a YAML file with **actors** (who is asking) and **probes** (the SQL each actor runs and what must happen).

```yaml
name: Document isolation

actors:
  - id: alice
    role: authenticated
    sub: 11111111-1111-1111-1111-111111111111
    claims: {role: authenticated}
  - id: bob
    role: authenticated
    sub: 22222222-2222-2222-2222-222222222222
    claims: {role: authenticated}

probes:
  - id: alice-sees-only-her-document
    actor: alice
    sql: SELECT id FROM public.documents ORDER BY id;
    expected_rows: [[1]]

  - id: bob-cannot-insert-for-alice
    actor: bob
    sql: INSERT INTO public.documents (id, owner_id, body) VALUES (11, '1111…', 'x');
    expect_error: row-level security policy
```

Validate offline with `rlsmatrix validate --manifest suite.yaml`.

## Actors

| Field | Meaning |
|---|---|
| `id` | Unique name, referenced by probes |
| `role` | PostgreSQL role the probe runs as |
| `sub` | Exposed as `request.jwt.claim.sub` |
| `claims` | Exposed as `request.jwt.claims`; `role` and `sub` are added automatically |

## Probes

| Field | Meaning |
|---|---|
| `id` | Unique name |
| `actor` | Must be a declared actor |
| `sql` | Exactly one `SELECT`, `INSERT`, `UPDATE` or `DELETE` |
| `expected_rows` | Exact, ordered result (default: no rows), so add `ORDER BY` |
| `expect_error` | Fragment the database error must contain; cannot be combined with `expected_rows` |

Each probe runs in a transaction that is rolled back. Keep fixture IDs fixed, because sequence values are not rolled back.

## Pitfall: `RETURNING` on a probe that expects an RLS error

`INSERT … RETURNING`, and an `UPDATE` that changes a row, must also satisfy the `SELECT` policy for the new row. A failure there produces the same message as a failed `WITH CHECK`:

```text
new row violates row-level security policy for table "documents"
```

The probe below therefore passes whether or not the insert policy is correct, and a widened `WITH CHECK` goes unnoticed:

```yaml
- id: bob-cannot-insert-for-alice
  actor: bob
  sql: INSERT INTO public.documents (id, owner_id, body) VALUES (11, '1111…', 'x') RETURNING id;
  expect_error: row-level security policy
```

**Fix:** drop `RETURNING` so only `WITH CHECK` can raise the error. For `UPDATE` policies, test the check with a row that stays visible to the actor, such as moving a project to an organization the actor can read but does not administer (the `org_projects` example does this). A surviving `OPEN_WITH_CHECK` mutation is how this gap shows up.

## Bundled examples

Five schemas ship in `src/rlsmatrix/examples/`. The web app loads them as presets, and the test suite validates every `suite*.yaml`.

| Schema | Suite | Operators | Mutations | Score | Adjusted |
|---|---|---|---:|---:|---:|
| `tenant_isolation` | `suite_first_draft.yaml` | core | 7 | 28.6% | 40.0% |
| `tenant_isolation` | `suite.yaml` | core | 7 | 71.4% | 100% |
| `org_projects` | `suite.yaml` | core | 16 | 100% | 100% |
| `support_tickets` | `suite.yaml` | core | 14 | 64.3% | 100% |
| `shared_notes` | `suite_first_draft.yaml` | core | 4 | 100% | 100% |
| `shared_notes` | `suite_first_draft.yaml` | core, predicate | 11 | 81.8% | 81.8% |
| `shared_notes` | `suite.yaml` | core, predicate | 11 | 100% | 100% |
| `owner_force_rls` | `suite.yaml` | all | 7 | 71.4% | 83.3% |
| `owner_force_rls` | `suite_no_owner.yaml` | all | 7 | 57.1% | 80.0% |

| Schema | Setup | Lesson |
|---|---|---|
| `tenant_isolation` | Two tenants, one table | In `suite.yaml` the two survivors are `WIDEN_TO_PUBLIC` changes that do nothing for `anon`, whose `auth.uid()` is `NULL`. The first-draft suite shows the opposite case: three of its five survivors are real gaps. |
| `org_projects` | Members, admins, a `RESTRICTIVE` policy, `SECURITY DEFINER` helpers | Scores 100% on core, yet `--operators WIDEN_COMMAND` shows nothing notices if the `RESTRICTIVE` `projects_hide_archived` policy is widened to every command. |
| `support_tickets` | Roles from a custom JWT claim (customer, agent, admin) | All five survivors are harmless: either for the same `anon` reason as above, or because an update policy's `WITH CHECK` equals its `USING`, so opening it never changes an outcome. |
| `shared_notes` | One compound policy: `(owner OR shared) AND NOT archived` | The first-draft suite kills every core mutation and looks finished. With `core,predicate`, two `DROP_CLAUSE` mutations survive as *changes behavior*: nothing checks the `archived` clause or the `shared` branch. `suite.yaml` adds one probe that closes both. |
| `owner_force_rls` | Table owner is also an application role, under `FORCE ROW LEVEL SECURITY` | `NO_FORCE_RLS` is caught only when an actor is the table owner. Without one it survives, and is deliberately left unlabelled rather than called harmless, because the equivalence check cannot see an owner you did not declare. |

A 100% score is not always the goal. Understanding each survivor is.
