# RLSMatrix

[![CI](https://img.shields.io/github/actions/workflow/status/rishipx/RLSMatrix/ci.yml?branch=main&label=CI&logo=githubactions&logoColor=white&style=flat-square)](https://github.com/rishipx/RLSMatrix/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11%E2%80%933.13-3776AB?style=flat-square&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)

**Mutation testing for PostgreSQL Row-Level Security.** RLSMatrix weakens your RLS policies one change at a time and reports every change your tests fail to catch.

<p align="center">
  <img src="docs/assets/web-app.png" alt="RLSMatrix web app showing surviving mutations" width="720">
</p>

## Why

RLS failures are silent. If a policy is weakened to `USING (true)`, Bob can read every row, but a test that only checks "Alice can read her own document" still passes.

```mermaid
flowchart LR
    A["🔐 Policy<br/>USING owner_id = auth.uid()"] -->|mutate| B["⚠️ USING (true)<br/>Bob can read every row"]
    B --> C{"Your tests"}
    C -->|"all still pass"| D["🟥 Survived<br/>missing test"]
    C -->|"one fails"| E["🟩 Killed<br/>covered"]

    classDef bad fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    classDef good fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef warn fill:#fef3c7,stroke:#d97706,color:#78350f
    class D bad
    class E good
    class B warn
```

RLSMatrix applies that change and others like it, then lists each one your suite misses.

## How it works

```mermaid
flowchart LR
    A["📄 Schema +<br/>YAML tests"] --> B["✅ Baseline<br/>must pass"]
    B --> C["🧬 Generate mutations<br/>from pg_catalog"]
    C --> D["🧪 Fresh database<br/>clone per mutation"]
    D --> E{"Any test<br/>fails?"}
    E -->|yes| F["🟩 Killed"]
    E -->|no| G["🟥 Survived"]
    G --> H["🔎 Classify<br/>survivor"]
    F --> I["📊 Score + report"]
    H --> I

    classDef good fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef bad fill:#fee2e2,stroke:#dc2626,color:#7f1d1d
    class F good
    class G bad
```

Mutations are rewritten with PostgreSQL's own parser, so every mutant is valid SQL.

| Result | Meaning |
|---|---|
| 🟩 **Killed** | A test failed, so the change was detected. |
| 🟥 **Survived: changes behavior** | Some actor now reads or writes differently. You are missing a probe. |
| 🟨 **Survived: likely equivalent** | No declared actor is affected. Left out of the *adjusted score*. |

```mermaid
mindmap
  root((11 operators))
    Whole policy
      OPEN_USING
      OPEN_WITH_CHECK
      DROP_POLICY
      DISABLE_RLS
    Predicate
      Inverted comparisons
      AND / OR swaps
      Dropped clauses
    Policy shape
      RESTRICTIVE to PERMISSIVE
      Widen to FOR ALL
      Remove FORCE RLS
```

```text
mutation score: 28.6%  (2 killed, 5 survived, 0 errors; 7 mutations in 1.7s)
adjusted score: 40.0%  (likely-equivalent survivors left out: 2)
  SURVIVED OPEN_WITH_CHECK  public.documents.documents_insert_own  [changes behavior]
  SURVIVED WIDEN_TO_PUBLIC  public.documents.documents_insert_own  [likely equivalent]
  KILLED   DROP_POLICY      public.documents.documents_insert_own  <- alice-can-insert-her-own-document
  ...
```

## Screenshots

**Write the suite.** Actors and probes are plain YAML, shown next to the schema they run against.

<img src="docs/assets/test-suite.png" alt="Test suite YAML editor listing actors and probes" width="720">

**See what your tests missed.** Each survivor shows the first behavioral difference, the exact SQL change, and the probe to add.

<img src="docs/assets/survivor-detail.png" alt="Expanded survivor: OPEN_WITH_CHECK on documents_insert_own, labelled changes behavior, with the ALTER POLICY statement and a suggested probe" width="720">

**Check coverage per probe.** The matrix shows which probe killed which mutation, and which mutations no probe noticed.

<img src="docs/assets/coverage-matrix.png" alt="Coverage matrix of mutations against probes, with killed and survived results" width="720">

<details>
<summary><h2>Quick start</h2></summary>

Requires Docker Engine and Docker Compose v2.

```bash
cp .env.example .env
# Set RLSMATRIX_DB_PASSWORD to a unique 24+ character value:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build        # web app at http://localhost:8501
```

Or run from the command line:

```bash
docker compose run --rm app rlsmatrix run \
  --bootstrap examples/tenant_isolation/schema.sql \
  --manifest  examples/tenant_isolation/suite.yaml \
  --min-score 70
```

Add `--operators all` to include predicate and policy-shape operators.

</details>

<details>
<summary><h2>GitHub Action</h2></summary>

```yaml
- uses: rishipx/RLSMatrix@v1.0.0
  with:
    bootstrap: db/schema.sql
    manifest: db/rls-suite.yaml
    min-score: "90"
```

</details>

## Security

RLSMatrix runs the SQL it is given and connects only to its own disposable database. It is not a sandbox for hostile input: run only SQL you trust.

```mermaid
flowchart LR
    U["👤 You"] -->|"127.0.0.1:8501"| A
    subgraph S["🔒 Internal Docker network, no internet"]
        A["App<br/>read-only · non-root"] --> P[("PostgreSQL 16<br/>tmpfs · disposable")]
    end
```

To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Limitations

| Not supported | Detail |
|---|---|
| pgTAP | Tests use RLSMatrix's YAML format. |
| Multi-step probes | A probe is a single SQL statement. |
| Non-policy objects | Operators target policies, not grants, views, functions or triggers. |

## Docs

[Usage](docs/usage.md) · [Writing suites](docs/writing-suites.md) · [Operators and results](docs/results.md) · [CI](docs/ci.md) · [Architecture](docs/architecture.md)

## License

[MIT](LICENSE)
