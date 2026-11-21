# Writing test suites

A suite is a YAML file with **actors** (who is asking) and **probes** (what they run, and what must happen).

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

## Actors

`role` is the PostgreSQL role the probe runs as. `sub` is exposed as `request.jwt.claim.sub`, and `claims` as `request.jwt.claims`. `role`, and `sub` when set, are added to the claims for you.

## Probes

- `sql` must be exactly one `SELECT`, `INSERT`, `UPDATE` or `DELETE`.
- `expected_rows` is an exact, ordered comparison (default: no rows), so add `ORDER BY`.
- `expect_error` is a fragment the database error must contain. It cannot be combined with `expected_rows`.
- Each probe runs in a transaction that is rolled back.

Probe IDs must be unique, and every probe must name a declared actor. Keep fixture IDs fixed: sequence values are not rolled back.

Check a suite without a database with `rlsmatrix validate --manifest suite.yaml`.

## Do not put `RETURNING` on a probe that expects an RLS error

`INSERT … RETURNING`, and an `UPDATE` that changes a row, must also pass the `SELECT` policy for the new row. That fails with the same message as a failed `WITH CHECK`:

```text
new row violates row-level security policy for table "documents"
```

So this probe passes whether or not the insert policy is correct, and a widened `WITH CHECK` goes unnoticed:

```yaml
- id: bob-cannot-insert-for-alice
  actor: bob
  sql: INSERT INTO public.documents (id, owner_id, body) VALUES (11, '1111…', 'x') RETURNING id;
  expect_error: row-level security policy
```

Drop the `RETURNING` so only `WITH CHECK` can produce the error. For `UPDATE` policies, test the check with a row that stays visible to the actor, for example moving a project to an organization the actor can read but does not administer. The `org_projects` example does this. A surviving `OPEN_WITH_CHECK` mutation is how this kind of gap shows up.
