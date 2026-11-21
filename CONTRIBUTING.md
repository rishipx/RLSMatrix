# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
make install
pre-commit install        # optional: formatting, lint and secret checks on commit
```

`make help` lists the tasks. The most useful are `make format`, `make lint`, `make typecheck`, `make test-unit`, and `make check`, which runs all of them plus the full test suite.

## Project layout

Source lives in `src/rlsmatrix/`, and [docs/architecture.md](docs/architecture.md) explains how the pieces fit. Tests mirror the package under `tests/unit/` (no database needed) and `tests/integration/` (needs the sandbox database).

## Integration tests

Integration tests and the UI test need PostgreSQL 16 reachable as the host `postgres` (the application refuses any other host). Without it they are skipped.

```bash
export RLSMATRIX_DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker run --rm -d --name rlsmatrix-pg -p 127.0.0.1:5432:5432 \
  -e POSTGRES_PASSWORD="$RLSMATRIX_DB_PASSWORD" postgres:16-alpine
echo "127.0.0.1 postgres" | sudo tee -a /etc/hosts
make test
```

Stop it with `docker stop rlsmatrix-pg`.

## Guidelines

- Keep database access limited to the Compose sandbox.
- Add tests for behavior changes, including security boundaries where relevant.
- Pass SQL values as parameters and build identifiers with `psycopg.sql.Identifier`.
- A new mutation operator needs an entry in `OPERATORS` and in `SURVIVOR_HINTS`, a case in the generator (predicate-level operators live in `mutations/predicates.py`), unit tests, and a row in [docs/results.md](docs/results.md). Make it opt-in, outside the `core` group, until the bundled examples have been run with it without errors.
- A new example goes in `src/rlsmatrix/examples/<name>/` with a `schema.sql` and a `suite.yaml`, and is added to `PRESETS` in `ui/presets.py` and to [docs/writing-suites.md#bundled-examples](docs/writing-suites.md#bundled-examples).
- Do not commit `.env` files, credentials or production data.

## Pull requests

Run `make check` first. The CI workflow runs lint, type checks, unit tests on Python 3.11 to 3.13, integration tests against PostgreSQL 16, a wheel install check and a Docker build.
