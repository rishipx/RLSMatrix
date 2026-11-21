-- Disposable fixture: a table whose owner is also an application role.
-- FORCE ROW LEVEL SECURITY makes the owner obey the policy like everyone else.
CREATE ROLE app_owner NOLOGIN;
CREATE ROLE reader NOLOGIN;

CREATE SCHEMA app AUTHORIZATION app_owner;

CREATE TABLE app.ledger (
  id integer PRIMARY KEY,
  account text NOT NULL,
  amount integer NOT NULL
);
ALTER TABLE app.ledger OWNER TO app_owner;

INSERT INTO app.ledger (id, account, amount) VALUES
  (1, 'public', 10),
  (2, 'private', 99);

ALTER TABLE app.ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.ledger FORCE ROW LEVEL SECURITY;

CREATE POLICY ledger_public_rows
  ON app.ledger
  FOR SELECT
  TO app_owner, reader
  USING (account = 'public');

GRANT USAGE ON SCHEMA app TO reader;
GRANT SELECT ON app.ledger TO reader;
