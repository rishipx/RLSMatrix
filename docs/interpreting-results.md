# Interpreting results

## Score

```text
mutation score = killed / (killed + survived) × 100
```

A mutation is **killed** if any assertion fails once it is applied, and **survived** if none does. A mutation that could not be evaluated is reported as an error and left out of the score.

## Real gaps and harmless changes

A surviving mutation is not always a problem. Widening a policy to `PUBLIC` changes nothing if the only extra role, `anon`, can never satisfy the predicate. RLSMatrix tells the two cases apart:

- **Changes behavior.** At least one actor can now read, update, delete or insert differently. The report names the first difference, for example *As alice, SELECT all rows on public.documents: 1 row(s) visible before the change, 2 row(s) visible after it.* That is the probe your suite is missing.
- **Likely equivalent.** No declared actor can do anything differently in your fixtures. Probably harmless, but "likely" is deliberate: the result depends on the actors and fixture rows you provided.

The **adjusted score** leaves the likely-equivalent survivors out. The plain score is never changed.

A survivor is a reason to review coverage, not proof of a vulnerability.

## How a survivor is assessed

RLSMatrix runs the same battery of statements on the baseline schema and on the mutated one, as every actor in your suite, on every table that has RLS enabled. Each statement runs in a transaction that is rolled back:

| Statement | What it exposes |
|---|---|
| `SELECT` every row | `USING` of read policies, and `RESTRICTIVE` policies |
| `DELETE` every row | `USING` of delete policies |
| `UPDATE` every row to itself | `USING` of update policies |
| `UPDATE` one column to each of up to three values found in the table | `WITH CHECK` of update policies, for example changing an owner |
| `INSERT` a copy of each of up to eight existing rows | `WITH CHECK` of insert policies |

Rows and values come from your fixtures. Comparing writes as well as reads matters: a read-only comparison would call every `OPEN_WITH_CHECK` survivor harmless, because a write check cannot change what an actor reads.

A difference is definite, since the change really does something. "Likely equivalent" is only as good as your actors and fixtures: a table with no rows, or no actor who is affected, makes every change look harmless. Add the actors and rows that matter and the verdict improves.

`NO_FORCE_RLS` is the exception. Removing `FORCE ROW LEVEL SECURITY` affects only the table owner, and the analysis cannot tell whether any declared actor is the owner, so a surviving `NO_FORCE_RLS` is never labelled likely equivalent.

## Limitations

- Assertions use RLSMatrix's own YAML format. It does not run pgTAP suites.
- Operators cover common weakening of policies. They do not touch grants, views, functions, triggers or the bodies of `SECURITY DEFINER` functions.
- The equivalence check only knows the actors and fixture rows you provide, and compares reads, deletes, updates and inserts on the tables themselves.
- A probe is a single SQL statement. Multi-step flows are not supported.
