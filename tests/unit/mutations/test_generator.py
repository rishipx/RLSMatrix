from rlsmatrix.mutations.generator import generate_mutations, quote_ident


def test_generates_predicate_role_and_table_mutations() -> None:
    policies = [
        {
            "schemaname": "public",
            "tablename": "docs",
            "policyname": "owner_only",
            "roles": ["authenticated"],
            "cmd": "ALL",
            "qual": "(owner_id = auth.uid())",
            "with_check": "(owner_id = auth.uid())",
        }
    ]
    tables = [
        {"schemaname": "public", "tablename": "docs", "rowsecurity": True},
        {"schemaname": "public", "tablename": "open_table", "rowsecurity": False},
    ]

    mutations = generate_mutations(policies, tables)
    kinds = {mutation.kind for mutation in mutations}

    assert kinds == {
        "OPEN_USING",
        "OPEN_WITH_CHECK",
        "WIDEN_TO_PUBLIC",
        "DISABLE_RLS",
        "DROP_POLICY",
    }
    assert len(mutations) == 5


def test_does_not_open_predicates_that_are_already_true() -> None:
    policies = [
        {
            "schemaname": "public",
            "tablename": "docs",
            "policyname": "public_read",
            "roles": ["public"],
            "cmd": "SELECT",
            "qual": "(true)",
            "with_check": None,
        }
    ]
    # Nothing to open or widen, but the policy can still be dropped.
    assert {m.kind for m in generate_mutations(policies, [])} == {"DROP_POLICY"}


def test_generates_mutation_for_implicit_update_with_check() -> None:
    policies = [
        {
            "schemaname": "public",
            "tablename": "docs",
            "policyname": "owner_update",
            "roles": ["authenticated"],
            "cmd": "UPDATE",
            "qual": "(owner_id = auth.uid())",
            "with_check": None,
        }
    ]
    mutations = generate_mutations(policies, [])
    assert {mutation.kind for mutation in mutations} == {
        "OPEN_USING",
        "OPEN_WITH_CHECK",
        "WIDEN_TO_PUBLIC",
        "DROP_POLICY",
    }
    with_check = next(item for item in mutations if item.kind == "OPEN_WITH_CHECK")
    assert "WITH CHECK (true)" in with_check.sql


def test_quotes_identifiers_safely() -> None:
    assert quote_ident('odd"name') == '"odd""name"'


def test_does_not_widen_restrictive_policy_to_public() -> None:
    policies = [
        {
            "schemaname": "public",
            "tablename": "docs",
            "policyname": "tenant_guard",
            "permissive": "RESTRICTIVE",
            "roles": ["authenticated"],
            "cmd": "SELECT",
            "qual": "(tenant_id = current_setting('app.tenant_id')::int)",
            "with_check": None,
        }
    ]
    mutations = generate_mutations(policies, [])
    assert "WIDEN_TO_PUBLIC" not in {mutation.kind for mutation in mutations}


def _policy(**overrides):
    base = {
        "schemaname": "public",
        "tablename": "notes",
        "policyname": "notes_select",
        "roles": ["authenticated"],
        "cmd": "SELECT",
        "qual": "((owner_id = auth.uid()) OR shared) AND (NOT archived)",
        "with_check": None,
    }
    return {**base, **overrides}


def test_predicate_mutations_rewrite_using_with_alter_policy() -> None:
    mutations = generate_mutations([_policy()], [], {"DROP_CLAUSE"})
    assert len(mutations) == 4
    for mutation in mutations:
        assert mutation.sql.startswith(
            'ALTER POLICY "notes_select" ON "public"."notes" USING ('
        )
        assert mutation.description.startswith("USING: ")
    assert len({m.id for m in mutations}) == len(mutations)


def test_predicate_mutations_cover_the_with_check_of_insert_policies() -> None:
    policy = _policy(cmd="INSERT", qual=None, with_check="(a = 1 AND b = 2)")
    mutations = generate_mutations([policy], [], {"FLIP_COMPARISON"})
    assert len(mutations) == 2
    assert all(" WITH CHECK (" in m.sql for m in mutations)


def test_all_operators_together_keep_ids_unique() -> None:
    policy = _policy(
        cmd="ALL", with_check="(a = 1 AND b = 2)", qual="(a = 1 AND b = 2)"
    )
    mutations = generate_mutations([policy], [], {"ALL"})
    assert len({m.id for m in mutations}) == len(mutations)
    assert {"OPEN_USING", "DROP_CLAUSE", "SWAP_BOOL_OP", "FLIP_COMPARISON"} <= {
        m.kind for m in mutations
    }


def test_restrictive_policy_can_become_permissive() -> None:
    policy = _policy(permissive="RESTRICTIVE", roles=["authenticated", "Role X"])
    mutation = next(
        m for m in generate_mutations([policy], [], {"RESTRICTIVE_TO_PERMISSIVE"})
    )
    assert mutation.sql.startswith('DROP POLICY "notes_select" ON "public"."notes"; ')
    assert "AS PERMISSIVE FOR SELECT" in mutation.sql
    assert 'TO "authenticated", "role x"' in mutation.sql


def test_permissive_policy_has_no_permissive_mutation() -> None:
    assert generate_mutations([_policy()], [], {"RESTRICTIVE_TO_PERMISSIVE"}) == []


def test_command_widening_keeps_predicates_and_skips_all_and_insert() -> None:
    mutations = generate_mutations([_policy()], [], {"WIDEN_COMMAND"})
    assert len(mutations) == 1
    assert "FOR ALL" in mutations[0].sql
    assert "USING (" in mutations[0].sql and "WITH CHECK" not in mutations[0].sql
    assert generate_mutations([_policy(cmd="ALL")], [], {"WIDEN_COMMAND"}) == []
    insert = _policy(cmd="INSERT", qual=None, with_check="(a = 1)")
    assert generate_mutations([insert], [], {"WIDEN_COMMAND"}) == []


def test_force_rls_is_only_removed_where_it_is_set() -> None:
    forced = {
        "schemaname": "app",
        "tablename": "ledger",
        "rowsecurity": True,
        "forcerowsecurity": True,
    }
    plain = {**forced, "tablename": "plain", "forcerowsecurity": False}
    mutations = generate_mutations([], [forced, plain], {"NO_FORCE_RLS"})
    assert [m.sql for m in mutations] == [
        'ALTER TABLE "app"."ledger" NO FORCE ROW LEVEL SECURITY'
    ]
