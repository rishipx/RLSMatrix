# Security policy

RLSMatrix is a local testing tool. It creates disposable PostgreSQL databases
in its own Docker Compose sandbox and is not meant to connect to production or
hosted databases. See the safety notes in the README before running custom SQL.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's
**Report a vulnerability** option on this repository's Security tab.

Include the version, the impact, steps to reproduce, and relevant logs, with any
credentials and production data removed.
