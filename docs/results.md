# Operators and results

- [Mutation operators](#mutation-operators)
- [Score](#score)
- [Gaps and harmless survivors](#gaps-and-harmless-survivors)
- [How survivors are assessed](#how-survivors-are-assessed)
- [Limitations](#limitations)

## Mutation operators

Each operator makes one kind of change to a policy or table. List them with `rlsmatrix operators`, and select them with `--operators`, which accepts operator names or the groups below, mixed freely (for example `core,predicate`).

| Group | Scope | Default |
|---|---|:---:|
| `core` | Replace or remove a whole policy | yes |
| `predicate` | Small changes inside a policy's expression | opt-in |
| `shape` | Policy or table configuration | opt-in |

`all` selects every group. Every surviving mutation is reported with a hint about the probe to add.

### Core

A reasonable suite catches these quickly.

| Operator | Change | A survivor usually means |
|---|---|---|
| `OPEN_USING` | `USING` becomes `TRUE` | No probe checks a user who must be denied |
| `OPEN_WITH_CHECK` | `WITH CHECK` becomes `TRUE`, including the implicit one on `UPDATE` and `ALL` policies | No probe attempts a write that must be rejected |
| `WIDEN_TO_PUBLIC` | Policy applies to `PUBLIC` instead of specific roles | No probe uses a role outside the `TO` list, or the change is equivalent |
| `DISABLE_RLS` | RLS is switched off on a table | No probe depends on RLS for that table |
| `DROP_POLICY` | The policy is deleted | No probe asserts the access the policy grants, so locking out legitimate users would go unnoticed |

### Predicate

Small edits of the kind that slip into real policies. They also apply inside subqueries such as `EXISTS (SELECT …)` membership checks. Predicates are parsed with PostgreSQL's own parser, so every mutation is valid SQL; a predicate that cannot be parsed is skipped.

| Operator | Change | A survivor usually means |
|---|---|---|
| `FLIP_COMPARISON` | One comparison or `NULL` test is inverted (`=` to `<>`, `<` to `>=`, `IS NULL` to `IS NOT NULL`) | No probe depends on that condition |
| `SWAP_BOOL_OP` | One `AND` becomes `OR`, or one `OR` becomes `AND` | No probe tells the two apart |
| `DROP_CLAUSE` | One clause is removed from an `AND` or `OR` chain | No probe needs that clause |

### Shape

PostgreSQL cannot do these with `ALTER POLICY`, so the policy is dropped and re-created.

| Operator | Change | A survivor usually means |
|---|---|---|
| `RESTRICTIVE_TO_PERMISSIVE` | A `RESTRICTIVE` policy becomes `PERMISSIVE` | No probe shows the policy narrowing access |
| `WIDEN_COMMAND` | A `SELECT`, `UPDATE` or `DELETE` policy becomes `FOR ALL` | No probe tries a command the policy was never meant to allow |
| `NO_FORCE_RLS` | `FORCE ROW LEVEL SECURITY` is removed | No actor is the table owner |

## Score

```text
mutation score = killed / (killed + survived) × 100
```

| Outcome | Meaning |
|---|---|
| **Killed** | At least one assertion fails once the mutation is applied |
| **Survived** | No assertion fails |
| **Error** | The mutation could not be applied or evaluated; excluded from the score |

## Gaps and harmless survivors

A survivor is a reason to review coverage, not proof of a vulnerability. For example, widening a policy to `PUBLIC` changes nothing if the only extra role, `anon`, can never satisfy the predicate.

| Label | Meaning |
|---|---|
| **Changes behavior** | At least one actor can now read, update, delete or insert differently. The report names the first difference, e.g. *As alice, SELECT all rows on public.documents: 1 row(s) visible before the change, 2 row(s) visible after it.* This is the probe your suite is missing. |
| **Likely equivalent** | No declared actor behaves differently in your fixtures. Probably harmless; "likely" is deliberate, because the verdict depends on the actors and rows you provided. |

The **adjusted score** leaves likely-equivalent survivors out. The plain score is never altered.

## How survivors are assessed

The same statements run on the baseline and the mutated schema, as every declared actor, on every table with RLS enabled. Each runs in a rolled-back transaction.

| Statement | Exposes |
|---|---|
| `SELECT` every row | `USING` of read policies; `RESTRICTIVE` policies |
| `DELETE` every row | `USING` of delete policies |
| `UPDATE` every row to itself | `USING` of update policies |
| `UPDATE` one column to each of up to three values found in the table | `WITH CHECK` of update policies, e.g. changing an owner |
| `INSERT` a copy of each of up to eight existing rows | `WITH CHECK` of insert policies |

Writes are compared as well as reads: a read-only comparison would call every `OPEN_WITH_CHECK` survivor harmless, because a write check cannot change what an actor reads.

**Reliability.** A difference is definite. "Likely equivalent" is only as good as your fixtures: a table with no rows, or no affected actor, makes every change look harmless. Add the actors and rows that matter to sharpen the verdict.

**Exception: `NO_FORCE_RLS`.** Removing `FORCE ROW LEVEL SECURITY` affects only the table owner, and the analysis cannot tell whether a declared actor is the owner. A surviving `NO_FORCE_RLS` is therefore never labelled likely equivalent.

## Limitations

- Assertions use RLSMatrix's YAML format; pgTAP suites are not run.
- Operators do not touch grants, views, functions, triggers or `SECURITY DEFINER` function bodies.
- The equivalence check knows only the actors and fixture rows you provide, and compares reads, deletes, updates and inserts on the tables themselves.
- A probe is a single SQL statement; multi-step flows are not supported.
