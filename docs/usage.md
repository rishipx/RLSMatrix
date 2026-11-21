# Usage

- [Install and run](#install-and-run)
- [Commands](#commands)
- [`run` options](#run-options)
- [Exit codes](#exit-codes)
- [Configuration](#configuration)

## Install and run

RLSMatrix runs against a disposable PostgreSQL server defined in its own Docker Compose project. **Requirements:** Docker Engine and Docker Compose v2.

### 1. Configure

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"   # copy into .env
```

Set `RLSMATRIX_DB_PASSWORD` in `.env` to a unique value of 24+ characters.

### 2. Run

**Web app**

```bash
docker compose up --build
```

Open <http://localhost:8501>, pick an example, and select **Run campaign**. Remove the sandbox with `docker compose down`.

**Command line**

```bash
docker compose run --rm app rlsmatrix run \
  --bootstrap examples/tenant_isolation/schema.sql \
  --manifest  examples/tenant_isolation/suite.yaml \
  --min-score 70
```

To use your own files, mount them into the container:

```bash
docker compose run --rm -v "$PWD/db:/work:ro" app rlsmatrix run \
  --bootstrap /work/schema.sql --manifest /work/suite.yaml
```

### Install as a package

```bash
pip install .          # command line
pip install ".[ui]"    # command line and web app (adds Streamlit and pandas)
```

RLSMatrix connects only to a PostgreSQL host named `postgres`. Outside Compose, provide a server under that name; see [CI](ci.md#without-compose).

## Commands

| Command | Purpose |
|---|---|
| `rlsmatrix run` | Run a mutation campaign |
| `rlsmatrix validate --manifest FILE` | Check a suite and its probe SQL without a database |
| `rlsmatrix operators` | List operators and their groups |

## `run` options

| Option | Description |
|---|---|
| `--bootstrap FILE` | Schema and fixture SQL (required) |
| `--manifest FILE` | YAML suite (required) |
| `--workers N` | Parallel workers, 1 to 16 (default 4) |
| `--operators A,B` | Operators or groups: `core` (default), `predicate`, `shape`, `all` |
| `--min-score PERCENT` | Exit with status 1 if the score is lower |
| `--exclude-equivalent` | Apply `--min-score` to the adjusted score |
| `--allow-errors` | Do not fail when some mutations could not be evaluated |
| `--format text\|json\|markdown` | Report format (default `text`) |
| `--output FILE` | Write the report to a file |
| `--quiet` | Suppress progress messages on stderr |

`markdown` suits a pull-request comment or `$GITHUB_STEP_SUMMARY`. `json` includes every probe result.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Score is below `--min-score` |
| `2` | Invalid usage |
| `3` | Baseline failed |
| `4` | Campaign could not run, an input could not be read, the report could not be written, or mutations could not be evaluated |

## Configuration

Settings are environment variables. With Compose, set them in `.env` (see `.env.example`). An invalid value stops the program with a message naming the variable.

| Variable | Default | Range | Purpose |
|---|---:|---|---|
| `RLSMATRIX_DB_PASSWORD` | required | 24+ characters | Sandbox database password |
| `RLSMATRIX_APP_PORT` | `8501` | | Web app port on `127.0.0.1` (Compose only) |
| `RLSMATRIX_WORKERS` | `4` | 1 to 16 | Parallel workers |
| `RLSMATRIX_STATEMENT_TIMEOUT_MS` | `5000` | 250 to 60000 | Time limit per probe |
| `RLSMATRIX_LOCK_TIMEOUT_MS` | `1500` | 100 to 30000 | Time limit waiting on a lock |
| `RLSMATRIX_CONNECT_TIMEOUT` | `5` | 1 to 30 | Seconds to wait for a connection |
| `RLSMATRIX_MAX_MUTATIONS` | `500` | 1 to 2000 | Largest campaign allowed |
| `RLSMATRIX_MAX_RESULT_ROWS` | `10000` | 1 to 100000 | Rows a probe may return |
| `RLSMATRIX_MAX_BOOTSTRAP_BYTES` | `1000000` | 1 to 10000000 | Largest schema script |
| `RLSMATRIX_MAX_MANIFEST_BYTES` | `512000` | 1 to 2000000 | Largest manifest |
| `RLSMATRIX_MAX_PROBE_SQL_BYTES` | `100000` | 1 to 1000000 | Largest probe statement |

The database host, port and maintenance database are fixed: RLSMatrix connects only to the `postgres` service of its own Compose project and refuses any other target.
