"""Build mutations from policy and table catalog rows."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Iterator
from dataclasses import dataclass
from typing import Any

from rlsmatrix.mutations.operators import (
    DISABLE_RLS,
    DROP_POLICY,
    NO_FORCE_RLS,
    OPEN_USING,
    OPEN_WITH_CHECK,
    RESTRICTIVE_TO_PERMISSIVE,
    SURVIVOR_HINTS,
    WIDEN_COMMAND,
    WIDEN_TO_PUBLIC,
    validate_operators,
)
from rlsmatrix.mutations.predicates import PREDICATE_OPERATORS, predicate_variants

_TRUE_EXPRESSIONS = frozenset({"true", "'t'::boolean", "1=1"})


@dataclass(frozen=True, slots=True)
class Mutation:
    id: str
    kind: str
    target: str
    description: str
    sql: str

    @property
    def hint(self) -> str:
        return SURVIVOR_HINTS.get(self.kind, "")


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _is_true(expression: str | None) -> bool:
    if expression is None:
        return True
    normalized = re.sub(r"[\s()]+", "", expression).lower()
    return normalized in _TRUE_EXPRESSIONS


def _mutation_id(kind: str, *parts: str) -> str:
    raw = "__".join((kind, *parts))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()[:54]
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{digest}"


def _role_list(roles: list[str]) -> str:
    if not roles or "public" in roles:
        return "PUBLIC"
    return ", ".join(quote_ident(role) for role in roles)


def _recreate_policy(policy: dict[str, Any], *, permissive: bool, command: str) -> str:
    """Drop and re-create a policy, since ALTER POLICY cannot change these."""
    schema = quote_ident(str(policy["schemaname"]))
    table = quote_ident(str(policy["tablename"]))
    name = quote_ident(str(policy["policyname"]))
    roles = [str(role).lower() for role in (policy.get("roles") or [])]
    parts = [
        f"CREATE POLICY {name} ON {schema}.{table}",
        f"AS {'PERMISSIVE' if permissive else 'RESTRICTIVE'}",
        f"FOR {command}",
        f"TO {_role_list(roles)}",
    ]
    if policy.get("qual") is not None:
        parts.append(f"USING ({policy['qual']})")
    if policy.get("with_check") is not None:
        parts.append(f"WITH CHECK ({policy['with_check']})")
    return f"DROP POLICY {name} ON {schema}.{table}; " + " ".join(parts)


def _policy_mutations(
    policy: dict[str, Any], enabled: frozenset[str]
) -> Iterator[Mutation]:
    schema = str(policy["schemaname"])
    table = str(policy["tablename"])
    name = str(policy["policyname"])
    target = f"{schema}.{table}.{name}"
    alter = (
        f"ALTER POLICY {quote_ident(name)} ON "
        f"{quote_ident(schema)}.{quote_ident(table)}"
    )

    def make(kind: str, description: str, statement: str) -> Mutation:
        return Mutation(
            _mutation_id(kind.lower(), schema, table, name),
            kind,
            target,
            description,
            statement,
        )

    command = str(policy.get("cmd") or "ALL").upper()
    qual = policy.get("qual")
    with_check = policy.get("with_check")
    roles = [str(role).lower() for role in (policy.get("roles") or [])]
    permissive = str(policy.get("permissive") or "PERMISSIVE").upper() == "PERMISSIVE"

    if qual is not None and not _is_true(str(qual)):
        yield make(
            OPEN_USING,
            "Replace the policy USING predicate with TRUE.",
            f"{alter} USING (true)",
        )

    # PostgreSQL reuses USING as the implicit WITH CHECK of UPDATE and ALL policies.
    effective_check = with_check
    if effective_check is None and command in {"ALL", "UPDATE"}:
        effective_check = qual
    if effective_check is not None and not _is_true(str(effective_check)):
        yield make(
            OPEN_WITH_CHECK,
            "Replace the effective policy WITH CHECK predicate with TRUE.",
            f"{alter} WITH CHECK (true)",
        )

    if permissive and "public" not in roles:
        yield make(
            WIDEN_TO_PUBLIC,
            "Change the policy target roles to PUBLIC without changing its predicate.",
            f"{alter} TO PUBLIC",
        )

    if not permissive:
        yield make(
            RESTRICTIVE_TO_PERMISSIVE,
            "Re-create the RESTRICTIVE policy as PERMISSIVE.",
            _recreate_policy(policy, permissive=True, command=command),
        )

    if command in {"SELECT", "UPDATE", "DELETE"} and qual is not None:
        yield make(
            WIDEN_COMMAND,
            f"Re-create the {command} policy as FOR ALL.",
            _recreate_policy(policy, permissive=permissive, command="ALL"),
        )

    wanted = enabled & PREDICATE_OPERATORS
    if wanted:
        for clause, expression in (("USING", qual), ("WITH CHECK", effective_check)):
            if expression is None or _is_true(str(expression)):
                continue
            for variant in predicate_variants(str(expression), wanted):
                yield Mutation(
                    _mutation_id(
                        variant.kind.lower(), schema, table, name, clause, variant.site
                    ),
                    variant.kind,
                    target,
                    f"{clause}: {variant.description}",
                    f"{alter} {clause} ({variant.expression})",
                )

    yield make(
        DROP_POLICY,
        "Delete the policy.",
        f"DROP POLICY {quote_ident(name)} ON "
        f"{quote_ident(schema)}.{quote_ident(table)}",
    )


def _table_mutations(table: dict[str, Any]) -> Iterator[Mutation]:
    if not bool(table.get("rowsecurity")):
        return
    schema = str(table["schemaname"])
    name = str(table["tablename"])
    if bool(table.get("forcerowsecurity")):
        yield Mutation(
            _mutation_id("no_force_rls", schema, name),
            NO_FORCE_RLS,
            f"{schema}.{name}",
            "Remove FORCE ROW LEVEL SECURITY from this table.",
            f"ALTER TABLE {quote_ident(schema)}.{quote_ident(name)} "
            "NO FORCE ROW LEVEL SECURITY",
        )
    yield Mutation(
        _mutation_id("disable_rls", schema, name),
        DISABLE_RLS,
        f"{schema}.{name}",
        "Disable row-level security on this table.",
        f"ALTER TABLE {quote_ident(schema)}.{quote_ident(name)} "
        "DISABLE ROW LEVEL SECURITY",
    )


def generate_mutations(
    policies: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    operators: Collection[str] | None = None,
) -> list[Mutation]:
    """Build the deterministic mutation list from catalog rows."""
    enabled = validate_operators(operators)
    candidates = [
        *(item for policy in policies for item in _policy_mutations(policy, enabled)),
        *(item for table in tables for item in _table_mutations(table)),
    ]
    return [item for item in candidates if item.kind in enabled]
