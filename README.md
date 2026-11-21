# RLSMatrix

[![CI](https://github.com/rishipx/RLSMatrix/actions/workflows/ci.yml/badge.svg)](https://github.com/rishipx/RLSMatrix/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Mutation testing for PostgreSQL Row-Level Security.

RLSMatrix checks whether your RLS tests are actually good. It breaks your policies on purpose, one change at a time, in a disposable database, and reruns your tests. If the tests still pass, they missed the break.

```text
RLSMatrix: First-draft suite (happy paths only)
baseline: passed
mutation score: 28.6%  (2 killed, 5 survived, 0 errors; 7 mutations in 1.7s)
adjusted score: 40.0%  (likely-equivalent survivors left out: 2)
  SURVIVED OPEN_WITH_CHECK  public.documents.documents_insert_own  [changes behavior]
  SURVIVED WIDEN_TO_PUBLIC  public.documents.documents_insert_own  [likely equivalent]
  KILLED   DROP_POLICY      public.documents.documents_insert_own  <- alice-can-insert-her-own-document
  SURVIVED OPEN_USING       public.documents.documents_select_own  [changes behavior]
  ...
```

Code coverage cannot tell you that nothing asserts "Bob must not read Alice's rows". A surviving mutation can.

## Features

- **Eleven mutation operators** in three groups: whole-policy changes, predicate-level changes (flipped comparisons, `AND`/`OR` swaps, dropped clauses, including inside subqueries), and policy-shape changes (`RESTRICTIVE` to `PERMISSIVE`, widening a policy to `FOR ALL`, removing `FORCE ROW LEVEL SECURITY`).
- **Real gap or harmless?** Survivors are compared with the baseline across reads, updates, deletes and inserts, so the report separates tests you are missing from changes that do nothing in your fixtures.
- **Safe to run.** A throwaway PostgreSQL container with no internet access, a fresh clone per mutation, validated SQL, and timeouts.
- **CI-ready.** `--min-score` gates a pipeline, Markdown and JSON reports are available, and the repository is also a GitHub Action.
- **Web app** for exploring results, built with Streamlit.

## Quick start

You need Docker Engine and Docker Compose v2.

```bash
cp .env.example .env
# Put a unique password of 24+ characters in .env:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build            # web app at http://localhost:8501
```

Or from the command line, with a score gate:

```bash
docker compose run --rm app rlsmatrix run \
  --bootstrap examples/tenant_isolation/schema.sql \
  --manifest  examples/tenant_isolation/suite.yaml \
  --min-score 70
```

Then try `--operators all` to add the predicate and shape operators.

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | Web app, command line and installation |
| [Writing test suites](docs/writing-suites.md) | Actors, probes and the YAML manifest |
| [Mutation operators](docs/mutation-operators.md) | Every change RLSMatrix makes |
| [Interpreting results](docs/interpreting-results.md) | Scores, real gaps and harmless survivors |
| [Command line](docs/command-line.md) | Options, report formats and exit codes |
| [Continuous integration](docs/continuous-integration.md) | The GitHub Action and a generic gate |
| [Configuration](docs/configuration.md) | Environment variables and limits |
| [Examples](docs/examples.md) | Five bundled schemas and what they show |
| [Architecture](docs/architecture.md) | How it works and how the code is organized |

## Safety

RLSMatrix runs SQL you give it, so it connects only to the disposable PostgreSQL service of its own Compose project and refuses any other host. Run only SQL you trust, and never reuse the sandbox password elsewhere. [Architecture](docs/architecture.md#safety-model) describes the full model, and [SECURITY.md](SECURITY.md) explains how to report a vulnerability.

## Limitations

Assertions use RLSMatrix's own YAML format and a probe is a single SQL statement. Operators cover common weakening of policies but not grants, views, functions or triggers. [Interpreting results](docs/interpreting-results.md#limitations) has the details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The bundled IBM Plex fonts are licensed under the SIL Open Font License; see `src/rlsmatrix/ui/static/`.
