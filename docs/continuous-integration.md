# Continuous integration

## GitHub Action

The repository is also a composite action. It starts a throwaway PostgreSQL container, runs a campaign, writes the Markdown report to the job summary, and fails the step if the score is below your threshold.

```yaml
jobs:
  rls:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rishipx/RLSMatrix@v1.0.0
        with:
          bootstrap: db/schema.sql
          manifest: db/rls-suite.yaml
          operators: core,predicate
          min-score: "90"
          exclude-equivalent: "true"
```

| Input | Default | Purpose |
|---|---|---|
| `bootstrap` | required | Path to the schema and fixture SQL |
| `manifest` | required | Path to the YAML suite |
| `operators` | `core` | Operators or groups: `core`, `predicate`, `shape`, `all` |
| `min-score` | none | Fail the step if the score is lower than this percentage |
| `exclude-equivalent` | `false` | Apply `min-score` to the adjusted score |
| `allow-errors` | `false` | Do not fail when some mutations could not be evaluated |
| `workers` | `4` | Parallel workers, 1 to 16 |
| `python-version` | `3.12` | Python used to run RLSMatrix |
| `postgres-image` | `postgres:16-alpine` | Image for the sandbox database |

The `score` output holds the mutation score as a percentage. The report logic lives in `scripts/action-run.sh`, which the integration tests exercise.

## A generic gate with Docker Compose

```yaml
- name: Prepare sandbox password
  run: |
    cp .env.example .env
    sed -i "s|CHANGE_ME|$(python -c 'import secrets; print(secrets.token_urlsafe(32))')|" .env

- name: RLS mutation gate
  run: |
    docker compose run --rm -v "$PWD/db:/work:ro" app rlsmatrix run \
      --bootstrap /work/schema.sql --manifest /work/suite.yaml \
      --min-score 90 --format markdown --quiet >> "$GITHUB_STEP_SUMMARY"

- name: Clean up
  if: always()
  run: docker compose down --volumes
```

## Without Compose

RLSMatrix connects only to a PostgreSQL host named `postgres`. On a CI runner, start a PostgreSQL 16 container, map the name, and set the password:

```bash
export RLSMATRIX_DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker run -d --name rlsmatrix-postgres -p 127.0.0.1:5432:5432 \
  -e POSTGRES_PASSWORD="$RLSMATRIX_DB_PASSWORD" \
  postgres:16-alpine postgres -c max_connections=120
echo "127.0.0.1 postgres" | sudo tee -a /etc/hosts
pip install .
rlsmatrix run --bootstrap db/schema.sql --manifest db/rls-suite.yaml --min-score 90
```
