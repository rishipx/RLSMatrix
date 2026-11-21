"""Mutation operator names, groups, descriptions and survivor hints."""

from __future__ import annotations

from collections.abc import Collection

from rlsmatrix.mutations.predicates import (
    DROP_CLAUSE,
    FLIP_COMPARISON,
    PREDICATE_OPERATORS,
    SWAP_BOOL_OP,
)

RESTRICTIVE_TO_PERMISSIVE = "RESTRICTIVE_TO_PERMISSIVE"
WIDEN_COMMAND = "WIDEN_COMMAND"
NO_FORCE_RLS = "NO_FORCE_RLS"

OPEN_USING = "OPEN_USING"
OPEN_WITH_CHECK = "OPEN_WITH_CHECK"
WIDEN_TO_PUBLIC = "WIDEN_TO_PUBLIC"
DISABLE_RLS = "DISABLE_RLS"
DROP_POLICY = "DROP_POLICY"

OPERATORS: dict[str, str] = {
    OPEN_USING: "A policy's USING predicate becomes TRUE (rows leak to readers).",
    OPEN_WITH_CHECK: "A policy's WITH CHECK predicate becomes TRUE (bad writes pass).",
    WIDEN_TO_PUBLIC: "A policy is retargeted from specific roles to PUBLIC.",
    DISABLE_RLS: "Row-level security is switched off for a table.",
    DROP_POLICY: "A policy is deleted, so legitimate access may stop working.",
    RESTRICTIVE_TO_PERMISSIVE: (
        "A RESTRICTIVE policy becomes PERMISSIVE, so it no longer narrows access."
    ),
    WIDEN_COMMAND: "A policy for one command (such as SELECT) is changed to FOR ALL.",
    NO_FORCE_RLS: "FORCE ROW LEVEL SECURITY is removed, so the table owner bypasses it.",
    FLIP_COMPARISON: "One comparison or NULL test in a predicate is inverted.",
    SWAP_BOOL_OP: "One AND in a predicate becomes OR, or one OR becomes AND.",
    DROP_CLAUSE: "One clause is removed from an AND or OR chain in a predicate.",
}

# Whole-policy operators. These run by default.
CORE_OPERATORS = frozenset(
    {OPEN_USING, OPEN_WITH_CHECK, WIDEN_TO_PUBLIC, DISABLE_RLS, DROP_POLICY}
)

# Operators that change how a policy or table is configured.
SHAPE_OPERATORS = frozenset({RESTRICTIVE_TO_PERMISSIVE, WIDEN_COMMAND, NO_FORCE_RLS})

# Selecting "core", "predicate", "shape" or "all" picks a whole group.
GROUPS: dict[str, frozenset[str]] = {
    "CORE": CORE_OPERATORS,
    "PREDICATE": PREDICATE_OPERATORS,
    "SHAPE": SHAPE_OPERATORS,
    "ALL": frozenset(OPERATORS),
}

# What a surviving mutation usually means, and what to add to the suite.
SURVIVOR_HINTS: dict[str, str] = {
    OPEN_USING: (
        "No probe reads or modifies rows through this policy as an actor who "
        "must be denied. Add a probe for a non-owning actor and assert the rows "
        "they must not see."
    ),
    OPEN_WITH_CHECK: (
        "No probe attempts a write that this check should reject. Add an "
        "INSERT or UPDATE as the wrong actor with expect_error: row-level security."
    ),
    WIDEN_TO_PUBLIC: (
        "No probe exercises a role outside this policy's TO list (for example "
        "anon). If the predicate is already false for those roles, the mutation "
        "is equivalent; otherwise add a probe for them."
    ),
    DISABLE_RLS: (
        "No probe depends on RLS for this table. Add a cross-tenant read that "
        "returns different rows with RLS enabled."
    ),
    DROP_POLICY: (
        "No probe asserts the access this policy grants, so removing it would go "
        "unnoticed. Add a probe for an actor who should be allowed."
    ),
    RESTRICTIVE_TO_PERMISSIVE: (
        "No probe shows this policy narrowing access. Add an actor that the other "
        "policies admit and this restriction must still reject."
    ),
    WIDEN_COMMAND: (
        "No probe tries a command this policy was never meant to allow. Add a write "
        "(or read) as an actor who may only do the policy's own command."
    ),
    NO_FORCE_RLS: (
        "No actor is the table owner. Add an owner-role actor and assert that RLS "
        "still limits what that role can see and change."
    ),
    FLIP_COMPARISON: (
        "No probe depends on this comparison. Add one actor the comparison must "
        "admit and one it must reject, and assert the rows each can see or write."
    ),
    SWAP_BOOL_OP: (
        "No probe tells AND from OR here. Add an actor who satisfies only one side "
        "of the condition and assert what that actor gets."
    ),
    DROP_CLAUSE: (
        "No probe needs this clause. Add an actor who passes every other clause but "
        "fails this one (or, in an OR chain, who passes only this one)."
    ),
}


def validate_operators(operators: Collection[str] | None) -> frozenset[str]:
    """Return the selected operators.

    ``None`` selects the core operators. Besides operator names, the group
    names ``core``, ``predicate``, ``shape`` and ``all`` are accepted.
    """
    if operators is None:
        return CORE_OPERATORS
    names = {item.strip().upper() for item in operators if item.strip()}
    unknown = sorted(names - OPERATORS.keys() - GROUPS.keys())
    if unknown:
        known = ", ".join([*OPERATORS, *(name.lower() for name in GROUPS)])
        raise ValueError(
            f"Unknown mutation operator(s): {', '.join(unknown)}. Known: {known}"
        )
    if not names:
        raise ValueError("Select at least one mutation operator.")
    selected: set[str] = set()
    for name in names:
        selected |= GROUPS.get(name, {name})
    return frozenset(selected)
