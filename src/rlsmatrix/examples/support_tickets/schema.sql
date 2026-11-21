-- Support tickets where authorization depends on a custom JWT claim
-- (app_role: customer, agent or admin) rather than on ownership alone.
-- Loaded only into disposable campaign databases.
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

-- Reads the custom claim the application puts in the JWT.
CREATE FUNCTION auth.app_role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'app_role'
$$;

CREATE TABLE public.tickets (
  id integer PRIMARY KEY,
  customer_id uuid NOT NULL,
  subject text NOT NULL,
  status text NOT NULL DEFAULT 'open'
);

INSERT INTO public.tickets (id, customer_id, subject, status) VALUES
  (1, '11111111-1111-1111-1111-111111111111', 'Cannot log in', 'open'),
  (2, '11111111-1111-1111-1111-111111111111', 'Invoice question', 'open'),
  (3, '22222222-2222-2222-2222-222222222222', 'Feature request', 'open');

ALTER TABLE public.tickets ENABLE ROW LEVEL SECURITY;

-- Customers see their own tickets. Agents and admins see every ticket.
CREATE POLICY tickets_select_own_or_staff ON public.tickets
  FOR SELECT TO authenticated
  USING (
    customer_id = auth.uid()
    OR auth.app_role() IN ('agent', 'admin')
  );

-- Customers open tickets for themselves only.
CREATE POLICY tickets_insert_own ON public.tickets
  FOR INSERT TO authenticated
  WITH CHECK (customer_id = auth.uid());

-- Only staff change tickets (status, subject, owner).
CREATE POLICY tickets_update_staff ON public.tickets
  FOR UPDATE TO authenticated
  USING (auth.app_role() IN ('agent', 'admin'))
  WITH CHECK (auth.app_role() IN ('agent', 'admin'));

-- Only admins delete tickets.
CREATE POLICY tickets_delete_admin ON public.tickets
  FOR DELETE TO authenticated
  USING (auth.app_role() = 'admin');

GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid(), auth.app_role() TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.tickets TO anon, authenticated, service_role;
