# Examples

Five schemas ship with RLSMatrix, in `src/rlsmatrix/examples/`. The web app loads them as presets, and every `suite*.yaml` is validated by the test suite.

| Schema | Suite | Operators | Mutations | Score | Adjusted |
|---|---|---|---:|---:|---:|
| `tenant_isolation`: two tenants, one table | `suite_first_draft.yaml`: happy paths only | core | 7 | 28.6% | 40.0% |
| `tenant_isolation` | `suite.yaml` | core | 7 | 71.4% | 100% |
| `org_projects`: members, admins, a `RESTRICTIVE` policy, `SECURITY DEFINER` helpers | `suite.yaml` | core | 16 | 100% | 100% |
| `support_tickets`: roles come from a custom JWT claim (customer, agent, admin) | `suite.yaml` | core | 14 | 64.3% | 100% |
| `shared_notes`: one compound policy, `(owner OR shared) AND NOT archived` | `suite_first_draft.yaml` | core | 4 | 100% | 100% |
| `shared_notes` | `suite_first_draft.yaml` | core, predicate | 11 | 81.8% | 81.8% |
| `shared_notes` | `suite.yaml` | core, predicate | 11 | 100% | 100% |
| `owner_force_rls`: a table owner that is also an application role, under `FORCE ROW LEVEL SECURITY` | `suite.yaml` | all | 7 | 71.4% | 83.3% |
| `owner_force_rls` | `suite_no_owner.yaml` | all | 7 | 57.1% | 80.0% |

## What each one shows

**`tenant_isolation`.** In `suite.yaml` the two survivors are `WIDEN_TO_PUBLIC` changes that do nothing for `anon`, whose `auth.uid()` is `NULL`. The first-draft suite shows the other case: three of its five survivors are real gaps.

**`support_tickets`.** All five survivors are harmless, either for the same reason or because an update policy's `WITH CHECK` is identical to its `USING`, so opening it can never change an outcome.

**`shared_notes`.** The first-draft suite kills every core mutation, so it looks finished. With `--operators core,predicate`, two `DROP_CLAUSE` mutations survive and are labelled as changing behavior: nothing checks the `archived` clause or the `shared` branch. `suite.yaml` adds one probe that closes both.

**`org_projects`.** It scores 100% on the core operators, yet `--operators WIDEN_COMMAND` shows that nothing notices if its `RESTRICTIVE` `projects_hide_archived` policy is widened to every command.

**`owner_force_rls`.** `NO_FORCE_RLS` is caught only when an actor is the table owner. Without one it survives, and it is deliberately left unlabelled instead of being called harmless, because the equivalence check cannot see an owner you did not declare.

A 100% score is not always the goal. Understanding each survivor is.
