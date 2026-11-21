# Getting started

RLSMatrix runs against a disposable PostgreSQL server that ships in its own Docker Compose project. You need Docker Engine and Docker Compose v2.

## Start the web app

```bash
cp .env.example .env
# Put a unique password of 24+ characters in .env:
python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build
```

Open <http://localhost:8501>, pick an example, and choose **Run campaign**. Remove the sandbox with `docker compose down`.

## Run from the command line

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

`--min-score` makes the command fail when the score is lower, so it can gate a CI pipeline. See [Command line](command-line.md) for every option.

## Install the package

The command line needs only the core dependencies. The web app adds Streamlit and pandas through the `ui` extra.

```bash
pip install .          # command line
pip install ".[ui]"    # command line and web app dependencies
```

RLSMatrix connects only to a PostgreSQL host named `postgres`, so outside Docker Compose you need a server reachable under that name. [Continuous integration](continuous-integration.md) shows how.

## Next steps

1. Read [Writing test suites](writing-suites.md) and adapt an [example](examples.md).
2. Run `rlsmatrix validate --manifest suite.yaml` to check a suite without a database.
3. Read [Interpreting results](interpreting-results.md) before acting on a survivor.
