# Mutation operators

Each operator makes one kind of change to a policy or table. List them with `rlsmatrix operators`.

## Core operators

These run by default. They replace or remove a whole policy, which a decent suite catches quickly.

| Operator | Change | A survivor usually means |
|---|---|---|
| `OPEN_USING` | `USING` becomes `TRUE` | No probe checks a user who must be denied |
| `OPEN_WITH_CHECK` | `WITH CHECK` becomes `TRUE`, including the implicit one on `UPDATE` and `ALL` policies | No probe attempts a write that must be rejected |
| `WIDEN_TO_PUBLIC` | The policy applies to `PUBLIC` instead of specific roles | No probe uses a role outside the `TO` list, or the mutation is equivalent |
| `DISABLE_RLS` | RLS is switched off on a table | No probe depends on RLS for that table |
| `DROP_POLICY` | The policy is deleted | No probe asserts the access the policy grants, so a change that locks legitimate users out would go unnoticed |

## Predicate operators

These make the small changes that slip into real policies. They work inside subqueries such as `EXISTS (SELECT ... )` membership checks. Predicates are parsed with PostgreSQL's own parser, so a mutation is always valid SQL, and a predicate that cannot be parsed is skipped, not guessed at.

| Operator | Change | A survivor usually means |
|---|---|---|
| `FLIP_COMPARISON` | One comparison or `NULL` test is inverted (`=` to `<>`, `<` to `>=`, `IS NULL` to `IS NOT NULL`) | No probe depends on that condition |
| `SWAP_BOOL_OP` | One `AND` becomes `OR`, or one `OR` becomes `AND` | No probe tells the two apart |
| `DROP_CLAUSE` | One clause is removed from an `AND` or `OR` chain | No probe needs that clause |

## Shape operators

These change how a policy or table is configured. PostgreSQL cannot do this with `ALTER POLICY`, so the policy is dropped and re-created.

| Operator | Change | A survivor usually means |
|---|---|---|
| `RESTRICTIVE_TO_PERMISSIVE` | A `RESTRICTIVE` policy becomes `PERMISSIVE` | No probe shows the policy narrowing access |
| `WIDEN_COMMAND` | A `SELECT`, `UPDATE` or `DELETE` policy becomes `FOR ALL` | No probe tries a command the policy was never meant to allow |
| `NO_FORCE_RLS` | `FORCE ROW LEVEL SECURITY` is removed | No actor is the table owner |

## Choosing operators

```bash
rlsmatrix run --bootstrap schema.sql --manifest suite.yaml --operators all
```

`--operators` takes operator names or the groups `core` (the default), `predicate`, `shape` and `all`. They can be mixed, for example `core,predicate`.

The groups other than `core` add mutations, so they are opt-in. Each surviving mutation is reported with a hint about the probe to add.
