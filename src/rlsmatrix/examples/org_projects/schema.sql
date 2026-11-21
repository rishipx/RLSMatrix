-- Disposable multi-tenant fixture: org membership, admin-only writes,
-- and a RESTRICTIVE policy. Loaded only into campaign databases.
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

CREATE TABLE public.org_members (
  org_id integer NOT NULL,
  user_id uuid NOT NULL,
  role text NOT NULL CHECK (role IN ('member', 'admin')),
  PRIMARY KEY (org_id, user_id)
);

CREATE TABLE public.projects (
  id integer PRIMARY KEY,
  org_id integer NOT NULL,
  name text NOT NULL,
  archived boolean NOT NULL DEFAULT false
);

INSERT INTO public.org_members (org_id, user_id, role) VALUES
  (1, '11111111-1111-1111-1111-111111111111', 'admin'),   -- alice: admin of org 1
  (1, '22222222-2222-2222-2222-222222222222', 'member'),  -- bob: member of org 1
  (2, '11111111-1111-1111-1111-111111111111', 'member'),  -- alice: only a member of org 2
  (2, '33333333-3333-3333-3333-333333333333', 'admin');   -- carol: admin of org 2

INSERT INTO public.projects (id, org_id, name, archived) VALUES
  (1, 1, 'Apollo', false),
  (2, 1, 'Borealis', false),
  (3, 2, 'Cygnus', false),
  (4, 1, 'Legacy (archived)', true);

-- SECURITY DEFINER helpers avoid recursive RLS on org_members.
CREATE FUNCTION public.is_org_member(p_org integer)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.org_members
    WHERE org_id = p_org AND user_id = auth.uid()
  )
$$;

CREATE FUNCTION public.is_org_admin(p_org integer)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.org_members
    WHERE org_id = p_org AND user_id = auth.uid() AND role = 'admin'
  )
$$;

ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY projects_select_members ON public.projects
  FOR SELECT TO authenticated
  USING (public.is_org_member(org_id));

CREATE POLICY projects_insert_members ON public.projects
  FOR INSERT TO authenticated
  WITH CHECK (public.is_org_member(org_id));

CREATE POLICY projects_update_admins ON public.projects
  FOR UPDATE TO authenticated
  USING (public.is_org_admin(org_id))
  WITH CHECK (public.is_org_admin(org_id));

CREATE POLICY projects_delete_admins ON public.projects
  FOR DELETE TO authenticated
  USING (public.is_org_admin(org_id));

-- Restrictive: ANDed with every permissive SELECT policy.
CREATE POLICY projects_hide_archived ON public.projects
  AS RESTRICTIVE
  FOR SELECT TO authenticated
  USING (NOT archived);

GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role;
REVOKE ALL ON FUNCTION public.is_org_member(integer), public.is_org_admin(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_org_member(integer), public.is_org_admin(integer)
  TO authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.projects TO anon, authenticated, service_role;
