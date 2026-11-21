-- Disposable tenant-isolation fixture. Loaded only into campaign databases.
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;

CREATE SCHEMA auth;
CREATE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid
$$;

CREATE TABLE public.documents (
  id integer PRIMARY KEY,
  owner_id uuid NOT NULL,
  body text NOT NULL
);

INSERT INTO public.documents (id, owner_id, body) VALUES
  (1, '11111111-1111-1111-1111-111111111111', 'Alice private document'),
  (2, '22222222-2222-2222-2222-222222222222', 'Bob private document');

ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY documents_select_own
  ON public.documents
  FOR SELECT
  TO authenticated
  USING (owner_id = auth.uid());

CREATE POLICY documents_insert_own
  ON public.documents
  FOR INSERT
  TO authenticated
  WITH CHECK (owner_id = auth.uid());

GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role;
GRANT SELECT, INSERT ON public.documents TO anon, authenticated, service_role;
