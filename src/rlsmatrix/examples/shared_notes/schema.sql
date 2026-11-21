-- Disposable shared-notes fixture. Loaded only into campaign databases.
-- One compound SELECT policy: own notes or shared notes, but never archived ones.
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

CREATE TABLE public.notes (
  id integer PRIMARY KEY,
  owner_id uuid NOT NULL,
  shared boolean NOT NULL DEFAULT false,
  archived boolean NOT NULL DEFAULT false,
  body text NOT NULL
);

INSERT INTO public.notes (id, owner_id, shared, archived, body) VALUES
  (1, '11111111-1111-1111-1111-111111111111', false, false, 'Alice private'),
  (2, '11111111-1111-1111-1111-111111111111', true,  false, 'Alice shared'),
  (3, '11111111-1111-1111-1111-111111111111', true,  true,  'Alice shared, archived'),
  (4, '22222222-2222-2222-2222-222222222222', false, false, 'Bob private'),
  (5, '22222222-2222-2222-2222-222222222222', true,  false, 'Bob shared');

ALTER TABLE public.notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY notes_select
  ON public.notes
  FOR SELECT
  TO authenticated
  USING ((owner_id = auth.uid() OR shared) AND NOT archived);

GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role;
GRANT SELECT ON public.notes TO anon, authenticated, service_role;
