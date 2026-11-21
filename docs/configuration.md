# Configuration

Settings come from environment variables. With Compose, put them in `.env`; see `.env.example`.

| Variable | Default | Range | Purpose |
|---|---:|---|---|
| `RLSMATRIX_DB_PASSWORD` | required | 24+ characters | Sandbox database password |
| `RLSMATRIX_APP_PORT` | `8501` | | Port for the web app on `127.0.0.1` (Compose only) |
| `RLSMATRIX_WORKERS` | `4` | 1 to 16 | Parallel workers |
| `RLSMATRIX_STATEMENT_TIMEOUT_MS` | `5000` | 250 to 60000 | Time limit for one probe |
| `RLSMATRIX_LOCK_TIMEOUT_MS` | `1500` | 100 to 30000 | Time limit for waiting on a lock |
| `RLSMATRIX_CONNECT_TIMEOUT` | `5` | 1 to 30 | Seconds to wait for a connection |
| `RLSMATRIX_MAX_MUTATIONS` | `500` | 1 to 2000 | Largest campaign allowed |
| `RLSMATRIX_MAX_RESULT_ROWS` | `10000` | 1 to 100000 | Rows a probe may return |
| `RLSMATRIX_MAX_BOOTSTRAP_BYTES` | `1000000` | 1 to 10000000 | Largest schema script |
| `RLSMATRIX_MAX_MANIFEST_BYTES` | `512000` | 1 to 2000000 | Largest manifest |
| `RLSMATRIX_MAX_PROBE_SQL_BYTES` | `100000` | 1 to 1000000 | Largest probe statement |

An invalid value stops the program with a message that names the variable.

The database host, port and maintenance database are fixed: RLSMatrix connects only to the `postgres` service of its own Compose project, and refuses any other target.
