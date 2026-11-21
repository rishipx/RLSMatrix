# Command line

Run it through Compose so it uses the sandbox database:

```bash
docker compose run --rm app rlsmatrix --help
docker compose run --rm -v "$PWD/db:/work:ro" app rlsmatrix run \
  --bootstrap /work/schema.sql --manifest /work/suite.yaml
```

## Commands

| Command | Purpose |
|---|---|
| `rlsmatrix run` | Run a campaign |
| `rlsmatrix validate` | Check a suite and its probe SQL without a database |
| `rlsmatrix operators` | List mutation operators and their groups |

## Options for `run`

| Option | Description |
|---|---|
| `--bootstrap FILE`, `--manifest FILE` | Schema SQL and YAML suite (both required) |
| `--workers N` | Parallel workers, 1 to 16 (default 4) |
| `--operators A,B` | Operators or groups to apply: `core` (default), `predicate`, `shape`, `all` |
| `--min-score PERCENT` | Exit with status 1 if the score is lower |
| `--exclude-equivalent` | Apply `--min-score` to the adjusted score, which leaves out likely-equivalent survivors |
| `--allow-errors` | Do not fail when some mutations could not be evaluated |
| `--format text\|json\|markdown` | Report format (default `text`) |
| `--output FILE` | Write the report to a file |
| `--quiet` | No progress messages on stderr |

The `markdown` format suits a pull-request comment or `$GITHUB_STEP_SUMMARY`. `json` contains every probe result.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | The score is below `--min-score` |
| `2` | Invalid usage |
| `3` | The baseline failed |
| `4` | The campaign could not run, an input could not be read, the report could not be written, or mutations could not be evaluated |
