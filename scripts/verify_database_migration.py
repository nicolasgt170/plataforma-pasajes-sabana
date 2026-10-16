"""Compare SQLite and PostgreSQL data, relations, aggregates, and sequences without writes."""
from __future__ import annotations

import argparse
import re
import os
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

EXPECTED_TABLES = (
    "admin_users", "buses", "companies", "company_fares", "login_attempts",
    "purchases", "routes", "simulated_payments", "tickets",
    "trip_schedules", "validations",
)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_value(value: Any, type_signature: str) -> Any:
    if isinstance(value, Decimal):
        return ("decimal", value.normalize())
    if isinstance(value, datetime):
        return ("datetime", value.isoformat(timespec="microseconds"))
    if isinstance(value, date):
        return ("date", value.isoformat())
    if isinstance(value, bool):
        return ("bool", value)
    if type_signature.startswith("numeric"):
        return ("decimal", Decimal(str(value)).normalize())
    if type_signature == "boolean":
        return ("bool", bool(value))
    if type_signature == "timestamp" and isinstance(value, str):
        return ("datetime", datetime.fromisoformat(value).isoformat(timespec="microseconds"))
    if type_signature == "date" and isinstance(value, str):
        return ("date", date.fromisoformat(value).isoformat())
    if type_signature in {"integer", "bigint", "smallint"}:
        return int(value)
    if type_signature in {"text", "char", "varchar"} or type_signature.startswith(("char(", "varchar(")):
        return str(value)
    if isinstance(value, bytes):
        return ("bytes", value.hex())
    return value


def source_aggregates(source_rows: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, tuple[int, Decimal]]]:
    result: dict[str, dict[str, tuple[int, Decimal]]] = {}
    for table_name, amount_column in (("purchases", "total_amount"), ("simulated_payments", "amount")):
        grouped: dict[str, list[Any]] = {}
        for row in source_rows[table_name]:
            status = str(row["status"])
            grouped.setdefault(status, []).append(Decimal(str(row[amount_column])))
        result[table_name] = {status: (len(values), sum(values, Decimal("0")))
                              for status, values in sorted(grouped.items())}
    return result


def normalize_type(value: Any) -> str:
    """Canonicalize equivalent SQLite declarations and PostgreSQL type names."""
    raw = str(value).strip().lower()
    size = re.search(r"\((\s*\d+\s*(?:,\s*\d+\s*)?)\)", raw)
    dimensions = tuple(int(part.strip()) for part in size.group(1).split(",")) if size else ()
    if "bool" in raw:
        return "boolean"
    if "timestamp" in raw or "datetime" in raw:
        return "timestamp"
    if re.search(r"\bdate\b", raw):
        return "date"
    if "numeric" in raw or "decimal" in raw:
        return "numeric" + (str(dimensions) if dimensions else "")
    if "double precision" in raw or "real" in raw or "float" in raw:
        return "float"
    if "character varying" in raw or "varchar" in raw:
        return "varchar" + (str(dimensions) if dimensions else "")
    if "char" in raw and "character varying" not in raw:
        return "char" + (str(dimensions) if dimensions else "")
    if "text" in raw or "clob" in raw:
        return "text"
    if "bytea" in raw or "blob" in raw:
        return "binary"
    if "bigint" in raw or re.search(r"\bint8\b", raw):
        return "bigint"
    if "smallint" in raw or re.search(r"\bint2\b", raw):
        return "smallint"
    if "int" in raw:
        return "integer"
    return re.sub(r"\s+", " ", raw)


def _strip_outer_parentheses(value: str) -> str:
    value = value.strip()
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        wraps_all = True
        in_quote = False
        for index, char in enumerate(value):
            if char == "'":
                in_quote = not in_quote
            if in_quote:
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    wraps_all = False
                    break
        if not wraps_all or depth != 0:
            break
        value = value[1:-1].strip()
    return value


def normalize_sql_fragment(value: Any) -> str:
    """Normalize whitespace/identifier quoting while preserving string literal contents."""
    raw = _strip_outer_parentheses(str(value or "").strip())
    parts = re.split(r"('(?:''|[^'])*')", raw)
    normalized = []
    for index, part in enumerate(parts):
        if index % 2:
            normalized.append(part)
        else:
            fragment = re.sub(r"::\s*(character varying|varchar|text|timestamp without time zone|timestamp|boolean|numeric|integer|bigint|smallint|regclass)\b(?:\s*\([^)]*\))?", "", part, flags=re.IGNORECASE)
            fragment = fragment.lower().replace('"', "")
            fragment = re.sub(r"\s*([(),=<>])\s*", r"\1", fragment)
            normalized.append(re.sub(r"\s+", "", fragment))
    return "".join(normalized)


def normalize_default(value: Any, type_signature: str, generated: bool = False) -> Any:
    if generated and (value is None or "nextval(" in str(value).lower()):
        return ("generated",)
    if value is None:
        return ("generated",) if generated else None
    raw = _strip_outer_parentheses(str(value))
    canonical = normalize_sql_fragment(raw)
    keyword = canonical.lower()
    if keyword in {"now()", "current_timestamp", "current_timestamp()"}:
        return ("expression", "current_timestamp")
    if type_signature == "boolean" and keyword in {"1", "true"}:
        return ("literal", True)
    if type_signature == "boolean" and keyword in {"0", "false"}:
        return ("literal", False)
    return ("sql", canonical)


def compare_table_schema(table_name: str, source: dict[str, Any], target: dict[str, Any]) -> list[str]:
    """Return property-level structural differences for one SQLite/PG table pair."""
    differences: list[str] = []
    source_columns, target_columns = source["columns"], target["columns"]
    for missing in sorted(source_columns.keys() - target_columns.keys()):
        differences.append(f"{table_name}: PostgreSQL column missing: {missing}")
    for extra in sorted(target_columns.keys() - source_columns.keys()):
        differences.append(f"{table_name}: unexpected PostgreSQL column: {extra}")
    for column in sorted(source_columns.keys() & target_columns.keys()):
        left, right = source_columns[column], target_columns[column]
        for property_name in ("type", "nullable", "default"):
            if left[property_name] != right[property_name]:
                differences.append(f"{table_name}.{column}: {property_name} differs (SQLite={left[property_name]!r}, PostgreSQL={right[property_name]!r})")
    for property_name, label in (("primary_key", "primary key column order"),
                                 ("unique_constraints", "UNIQUE constraints"),
                                 ("indexes", "indexes/unique/indexed columns"),
                                 ("foreign_keys", "foreign keys")):
        if source[property_name] != target[property_name]:
            differences.append(f"{table_name}: {label} differs (SQLite={source[property_name]!r}, PostgreSQL={target[property_name]!r})")
    return differences


def sqlite_table_schema(con: sqlite3.Connection, table_name: str) -> dict[str, Any]:
    table_q = quote(table_name)
    info = con.execute(f"PRAGMA table_info({table_q})").fetchall()
    pk = tuple(row["name"] for row in sorted((r for r in info if r["pk"]), key=lambda r: r["pk"]))
    columns = {}
    for row in info:
        signature = normalize_type(row["type"])
        effective_nullable = not bool(row["notnull"] or row["pk"])
        auto_pk = (len(pk) == 1 and row["name"] == pk[0] and signature == "integer"
                   and row["dflt_value"] is None)
        columns[row["name"]] = {
            "type": signature,
            "nullable": effective_nullable,
            "default": normalize_default(row["dflt_value"], signature, generated=auto_pk),
        }
    uniques, indexes = [], []
    for index in con.execute(f"PRAGMA index_list({table_q})").fetchall():
        index_name = index["name"]
        index_q = quote(index_name)
        parts = con.execute(f"PRAGMA index_xinfo({index_q})").fetchall()
        key_parts = sorted((part for part in parts if part["key"]), key=lambda part: part["seqno"])
        col_names = tuple(part["name"] for part in key_parts)
        origin = index["origin"]
        if origin == "u":
            uniques.append(tuple(sorted(col_names)))
        elif origin == "c":
            create_sql = con.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index_name,)).fetchone()[0]
            if any(name is None for name in col_names):
                expression = normalize_sql_fragment(create_sql)
                col_names = ("<expression>", expression)
            where = re.search(r"\bwhere\b(.+)$", create_sql or "", flags=re.IGNORECASE)
            predicate = normalize_sql_fragment(where.group(1)) if where else ""
            indexes.append((col_names, (), bool(index["unique"]), bool(index["partial"]), predicate))
    foreign_groups: dict[int, list[sqlite3.Row]] = {}
    for row in con.execute(f"PRAGMA foreign_key_list({table_q})").fetchall():
        foreign_groups.setdefault(row["id"], []).append(row)
    foreign_keys = []
    for entries in foreign_groups.values():
        ordered = sorted(entries, key=lambda item: item["seq"])
        foreign_keys.append((tuple(item["from"] for item in ordered), ordered[0]["table"],
                             tuple(item["to"] for item in ordered), ordered[0]["on_update"].upper(),
                             ordered[0]["on_delete"].upper(),
                             "SIMPLE" if ordered[0]["match"].upper() in {"NONE", "SIMPLE"} else ordered[0]["match"].upper()))
    return {"columns": columns, "primary_key": pk,
            "unique_constraints": tuple(sorted(uniques)), "indexes": tuple(sorted(indexes, key=repr)),
            "foreign_keys": tuple(sorted(foreign_keys))}


def postgres_table_schema(con: Any, inspector: Any, table_name: str) -> dict[str, Any]:
    columns_meta = inspector.get_columns(table_name, schema="public")
    pk = tuple(inspector.get_pk_constraint(table_name, schema="public").get("constrained_columns") or ())
    columns = {}
    for column in columns_meta:
        signature = normalize_type(column["type"])
        is_pk = column["name"] in pk
        default = column.get("default")
        generated = bool(column.get("identity")) or (is_pk and isinstance(default, str) and "nextval(" in default.lower())
        columns[column["name"]] = {
            "type": signature,
            "nullable": bool(column["nullable"]) and not is_pk,
            "default": normalize_default(default, signature, generated=generated),
        }
    uniques = [tuple(sorted(item["column_names"])) for item in inspector.get_unique_constraints(table_name, schema="public")]
    indexes = []
    for item in inspector.get_indexes(table_name, schema="public"):
        cols = tuple(item.get("column_names") or ())
        options = item.get("dialect_options") or {}
        predicate = options.get("postgresql_where")
        included = tuple(options.get("postgresql_include") or ())
        expressions = tuple(item.get("expressions") or ())
        if expressions:
            cols = ("<expression>", *(normalize_sql_fragment(expr) for expr in expressions))
        indexes.append((cols, included, bool(item.get("unique")), bool(predicate), normalize_sql_fragment(predicate) if predicate else ""))
    foreign_keys = []
    for item in inspector.get_foreign_keys(table_name, schema="public"):
        options = item.get("options") or {}
        foreign_keys.append((tuple(item["constrained_columns"]), item["referred_table"],
                             tuple(item["referred_columns"]), str(options.get("onupdate", "NO ACTION")).upper(),
                             str(options.get("ondelete", "NO ACTION")).upper(),
                             str(options.get("match", "SIMPLE")).upper()))
    return {"columns": columns, "primary_key": pk,
            "unique_constraints": tuple(sorted(uniques)), "indexes": tuple(sorted(indexes, key=repr)),
            "foreign_keys": tuple(sorted(foreign_keys))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("pasajes_pre_migracion_backup.db"))
    parser.add_argument("--target-url-env", default="MIGRATION_TARGET_URL", help="Environment variable containing URL; never logged.")
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--expected-port", type=int, default=5432)
    parser.add_argument("--expected-database", required=True)
    parser.add_argument("--expected-user", required=True)
    parser.add_argument("--target-network", choices=("local", "render-internal", "external"), required=True)
    parser.add_argument("--allow-remote", action="store_true", help="Explicitly allow the reviewed non-local destination.")
    args = parser.parse_args()
    raw_url = os.environ.get(args.target_url_env, "")
    if not raw_url:
        parser.error(f"Environment variable {args.target_url_env} is required; URL values are never accepted as arguments")
    try:
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port or 5432
        username = unquote(parsed.username or "")
        dbname = unquote(parsed.path.lstrip("/").split("/", 1)[0])
        sslmode = parse_qs(parsed.query).get("sslmode", [""])[-1].lower()
    except ValueError:
        parser.error("Target URL is malformed; its value is not displayed")
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or not parsed.username or not parsed.password:
        parser.error("Target must be a PostgreSQL URL with credentials supplied through the environment")
    expected_host = args.expected_host.lower().rstrip(".")
    if host != expected_host or dbname != args.expected_database:
        parser.error("Target host or database does not match the explicitly approved destination")
    if username != args.expected_user:
        parser.error("Target role does not match the explicitly approved migration role")
    if port != args.expected_port:
        parser.error("Target port does not match the explicitly approved destination")
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if args.target_network == "local" and not loopback:
        parser.error("--target-network local requires a loopback hostname")
    if args.target_network != "local" and loopback:
        parser.error("A remote network mode cannot use a loopback hostname")
    if args.target_network != "local" and not args.allow_remote:
        parser.error("Remote target refused; --allow-remote is required after destination review")
    if args.target_network == "external" and sslmode not in {"require", "verify-ca", "verify-full"}:
        parser.error("External PostgreSQL connections require sslmode=require or stronger")

    source = args.source.resolve(strict=True)
    src = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    try:
        source_issues = []
        integrity = src.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            source_issues.append(f"SQLite integrity_check failed: {integrity}")
        source_tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if source_tables != set(EXPECTED_TABLES):
            source_issues.append(f"SQLite table names differ (expected={sorted(EXPECTED_TABLES)!r}, actual={sorted(source_tables)!r})")
        fk_issues = src.execute("PRAGMA foreign_key_check").fetchall()
        if fk_issues:
            source_issues.append(f"SQLite foreign-key violations: {[(r[0], r[1], r[2], r[3]) for r in fk_issues]!r}")
        if source_issues:
            print("VERIFICATION FAILED:")
            for issue in source_issues:
                print(f"  {issue}")
            return 1
        source_rows: dict[str, list[dict[str, Any]]] = {}
        source_counts: dict[str, int] = {}
        raw_rows: dict[str, list[dict[str, Any]]] = {}
        source_schemas: dict[str, dict[str, Any]] = {}
        for name in EXPECTED_TABLES:
            source_schemas[name] = sqlite_table_schema(src, name)
            pk = source_schemas[name]["primary_key"]
            if not pk:
                raise RuntimeError(f"No primary key defined for {name}")
            order = ", ".join(quote(column) for column in pk)
            fetched = src.execute(f"SELECT * FROM {quote(name)} ORDER BY {order}").fetchall()
            raw_rows[name] = [dict(row) for row in fetched]
            source_rows[name] = raw_rows[name]
            source_counts[name] = len(fetched)
    finally:
        src.close()
    expected_aggregates = source_aggregates(raw_rows)

    try:
        from sqlalchemy import create_engine, inspect, text
    except ImportError:
        raise SystemExit("SQLAlchemy is required to verify PostgreSQL; no target was opened.") from None
    engine = create_engine(raw_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    errors: list[str] = []
    try:
        with engine.connect() as con:
            actual_db = con.execute(text("SELECT current_database()" )).scalar_one()
            if actual_db != args.expected_database:
                raise RuntimeError("Connected database name differs from the approved destination")
            actual_user = con.execute(text("SELECT current_user" )).scalar_one()
            if actual_user != args.expected_user:
                raise RuntimeError("Connected role differs from the approved migration role")
            con.exec_driver_sql("SET LOCAL search_path TO public")
            inspector = inspect(con)
            target_tables = set(inspector.get_table_names(schema="public"))
            if target_tables != set(EXPECTED_TABLES):
                errors.append(f"PostgreSQL public table names differ (missing={sorted(set(EXPECTED_TABLES) - target_tables)!r}, extra={sorted(target_tables - set(EXPECTED_TABLES))!r})")
            other_user_tables = {
                (row[0], row[1]) for row in con.exec_driver_sql("""
                    SELECT n.nspname, c.relname
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'public')
                      AND n.nspname NOT LIKE 'pg_toast%'
                      AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                """).fetchall()
            }
            if other_user_tables:
                errors.append(f"Unexpected user tables exist outside public schema: {sorted(other_user_tables)!r}")
            counts: dict[str, int] = {}
            for name in EXPECTED_TABLES:
                if name not in target_tables:
                    continue
                target_schema = postgres_table_schema(con, inspector, name)
                errors.extend(compare_table_schema(name, source_schemas[name], target_schema))
                target_counts = int(con.exec_driver_sql(f"SELECT count(*) FROM public.{quote(name)}").scalar_one())
                counts[name] = target_counts
                if source_counts[name] != counts[name]:
                    errors.append(f"{name}: row count differs (SQLite {source_counts[name]}, PostgreSQL {counts[name]})")
                source_columns, target_columns = source_schemas[name]["columns"], target_schema["columns"]
                common_columns = sorted(source_columns.keys() & target_columns.keys())
                comparable_types = all(source_columns[column]["type"] == target_columns[column]["type"] for column in common_columns)
                if common_columns and comparable_types:
                    select_cols = ", ".join(quote(column) for column in common_columns)
                    result = con.exec_driver_sql(f"SELECT {select_cols} FROM public.{quote(name)}").fetchall()
                    source_values = [tuple(normalize_value(row[column], source_columns[column]["type"]) for column in common_columns)
                                     for row in source_rows[name]]
                    target_values = [tuple(normalize_value(value, source_columns[column]["type"]) for column, value in zip(common_columns, row))
                                     for row in result]
                    source_values.sort(key=repr)
                    target_values.sort(key=repr)
                    if source_values != target_values:
                        for row_index, (source_row, target_row) in enumerate(zip(source_values, target_values)):
                            if source_row != target_row:
                                changed = [column for column, left, right in zip(common_columns, source_row, target_row) if left != right]
                                errors.append(f"{name}: row values differ at sorted row {row_index}; column(s): {', '.join(changed)}")
                                break

            for name in sorted(target_tables & set(EXPECTED_TABLES)):
                for fk in inspector.get_foreign_keys(name, schema="public"):
                    child_columns = fk.get("constrained_columns") or []
                    parent_columns = fk.get("referred_columns") or []
                    parent_table = fk.get("referred_table")
                    if not parent_table or not child_columns or len(child_columns) != len(parent_columns) or parent_table not in target_tables:
                        errors.append(f"{name}: foreign key has an incomplete or missing target definition")
                        continue
                    joins = " AND ".join(f"c.{quote(child)}=p.{quote(parent)}" for child, parent in zip(child_columns, parent_columns))
                    all_nonnull = " AND ".join(f"c.{quote(child)} IS NOT NULL" for child in child_columns)
                    bad = con.exec_driver_sql(
                        f"SELECT count(*) FROM public.{quote(name)} c LEFT JOIN public.{quote(parent_table)} p ON {joins} "
                        f"WHERE {all_nonnull} AND p.{quote(parent_columns[0])} IS NULL"
                    ).scalar_one()
                    if bad:
                        errors.append(f"{name}.{','.join(child_columns)}: {bad} PostgreSQL foreign-key violation(s)")

            actual_aggregates: dict[str, dict[str, tuple[int, Decimal]]] = {}
            for table_name, amount_column in (("purchases", "total_amount"), ("simulated_payments", "amount")):
                if table_name not in target_tables:
                    actual_aggregates[table_name] = {}
                    continue
                rows = con.execute(text(
                    f'SELECT status, count(*) AS row_count, coalesce(sum("{amount_column}"), 0) AS amount_sum '
                    f'FROM public."{table_name}" GROUP BY status ORDER BY status'
                )).fetchall()
                actual_aggregates[table_name] = {str(row.status): (int(row.row_count), Decimal(str(row.amount_sum))) for row in rows}
            for table_name in ("purchases", "simulated_payments"):
                if expected_aggregates[table_name] != actual_aggregates[table_name]:
                    errors.append(f"{table_name}: aggregate record counts or amount totals grouped by status differ")

            for table_name in EXPECTED_TABLES:
                pks = source_schemas[table_name]["primary_key"]
                if table_name not in target_tables or len(pks) != 1:
                    continue
                pk = pks[0]
                pk_type = source_schemas[table_name]["columns"][pk]["type"]
                if pk_type not in {"integer", "bigint", "smallint"}:
                    continue
                seq = con.execute(text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                                  {"table_name": f"public.{table_name}", "column_name": pk}).scalar_one_or_none()
                max_id = con.exec_driver_sql(f"SELECT max({quote(pk)}) FROM public.{quote(table_name)}").scalar_one()
                if not seq:
                    errors.append(f"{table_name}.{pk}: no owned PostgreSQL sequence found")
                    continue
                seq_info = con.execute(text("""
                    SELECT n.nspname AS schema_name, c.relname AS sequence_name
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE c.oid = CAST(:seq AS regclass)
                """), {"seq": seq}).mappings().one_or_none()
                if not seq_info:
                    errors.append(f"{table_name}.{pk}: sequence catalog entry missing")
                    continue
                state = con.exec_driver_sql(
                    f'SELECT last_value, is_called FROM {quote(seq_info["schema_name"])}.{quote(seq_info["sequence_name"])}'
                ).mappings().one()
                start_value = con.execute(text("""
                    SELECT start_value FROM pg_catalog.pg_sequences
                    WHERE schemaname=:schema_name AND sequencename=:sequence_name
                """), {"schema_name": seq_info["schema_name"], "sequence_name": seq_info["sequence_name"]}).scalar_one_or_none()
                if max_id is None:
                    if state["is_called"] or start_value is None or int(state["last_value"]) != int(start_value):
                        errors.append(f"{table_name}.{pk}: empty table sequence differs from its uncalled start value")
                elif int(state["last_value"]) != int(max_id) or not state["is_called"]:
                    errors.append(f"{table_name}.{pk}: sequence position differs from max id {max_id}")

        print("ROW COUNTS")
        for name in EXPECTED_TABLES:
            print(f"  {name}: SQLite={source_counts[name]}, PostgreSQL={counts.get(name, 'missing')}")
        print("PURCHASE AND PAYMENT TOTALS BY STATUS")
        for table_name in ("purchases", "simulated_payments"):
            print(f"  {table_name}:")
            for status in sorted(set(expected_aggregates[table_name]) | set(actual_aggregates.get(table_name, {}))):
                print(f"    {status}: SQLite={expected_aggregates[table_name].get(status, (0, Decimal('0')))}, PostgreSQL={actual_aggregates.get(table_name, {}).get(status, (0, Decimal('0')))}")
        if errors:
            print("VERIFICATION FAILED:")
            for error in errors:
                print(f"  {error}")
            return 1
        print("VERIFICATION PASSED: tables, columns, row counts and values, FK definitions/integrity, aggregates, and sequences match.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"VERIFICATION FAILED (stopped: {type(exc).__name__}); URL and credentials were not logged.", file=sys.stderr)
        raise SystemExit(1) from None
