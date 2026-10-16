"""Copy the approved SQLite source into an empty PostgreSQL database (dry run by default)."""
from __future__ import annotations

import argparse
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


def read_source(path: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    source = path.resolve(strict=True)
    con = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(EXPECTED_TABLES):
            raise RuntimeError(f"Source table set differs from expected 11 tables: {sorted(tables)}")
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(f"SQLite foreign_key_check found {len(fk_errors)} violation(s)")
        rows, counts = {}, {}
        for name in EXPECTED_TABLES:
            quoted = '"' + name.replace('"', '""') + '"'
            result = con.execute(f"SELECT * FROM {quoted} ORDER BY rowid").fetchall()
            rows[name], counts[name] = [dict(r) for r in result], len(result)
        return rows, counts
    finally:
        con.close()


def models_metadata():
    # app.models imports app.database. Pin only that import to in-memory SQLite,
    # then restore the process environment exactly as it was.
    had_database_url = "DATABASE_URL" in os.environ
    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    try:
        from app.models import Base
    finally:
        if had_database_url:
            os.environ["DATABASE_URL"] = prior_database_url or ""
        else:
            os.environ.pop("DATABASE_URL", None)
    return Base


def convert(value: Any, column: Any) -> Any:
    if value is None:
        return None
    kind = type(column.type).__name__.lower()
    if kind == "numeric":
        return Decimal(str(value))
    if kind == "boolean":
        return bool(value)
    if kind == "datetime" and isinstance(value, str):
        return datetime.fromisoformat(value)
    if kind == "date" and isinstance(value, str):
        return date.fromisoformat(value)
    if kind in {"integer", "biginteger", "smallinteger"}:
        return int(value)
    if kind in {"string", "text"}:
        return str(value)
    return value


def resolve_target(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str | None:
    raw_url = os.environ.get(args.target_url_env, "")
    if not raw_url:
        if args.apply:
            parser.error(f"Environment variable {args.target_url_env} is required for apply; URL values are never accepted as arguments")
        return None
    try:
        parsed = urlsplit(raw_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port or 5432
        dbname = unquote(parsed.path.lstrip("/").split("/", 1)[0])
        query = parse_qs(parsed.query)
    except ValueError:
        parser.error("Target URL is malformed; its value is not displayed")
    if parsed.scheme not in {"postgresql", "postgresql+psycopg"} or not parsed.username or not parsed.password:
        parser.error("Target must be a PostgreSQL URL with credentials supplied through the environment")
    if not args.expected_host or not args.expected_database or not args.expected_user:
        parser.error("When a target URL is configured, expected host, database, and user are required")
    expected_host = args.expected_host.lower().rstrip(".")
    if host != expected_host or dbname != args.expected_database:
        parser.error("Target host or database does not match the explicitly approved destination")
    if unquote(parsed.username or "") != args.expected_user:
        parser.error("Target role does not match the explicitly approved migration role")
    if port != args.expected_port:
        parser.error("Target port does not match the explicitly approved destination")
    is_loopback = host in {"localhost", "127.0.0.1", "::1"}
    if args.target_network == "local" and not is_loopback:
        parser.error("--target-network local requires a loopback hostname")
    if args.target_network != "local" and is_loopback:
        parser.error("A remote network mode cannot use a loopback hostname")
    if args.target_network != "local" and not args.allow_remote:
        parser.error("Remote target refused; --allow-remote is required after destination review")
    sslmode = query.get("sslmode", [""])[-1].lower()
    if args.target_network == "external" and sslmode not in {"require", "verify-ca", "verify-full"}:
        parser.error("External PostgreSQL connections require sslmode=require or stronger")
    return raw_url


def reject_existing_objects(con: Any) -> None:
    rows = con.exec_driver_sql("""
        SELECT n.nspname, c.relname, c.relkind
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
        ORDER BY n.nspname, c.relname
    """).fetchall()
    if rows:
        raise RuntimeError("Destination contains pre-existing user relations; refusing to modify it")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("pasajes_pre_migracion_backup.db"))
    parser.add_argument("--target-url-env", default="MIGRATION_TARGET_URL", help="Environment variable containing the URL; never logged.")
    parser.add_argument("--expected-host", help="Exact approved PostgreSQL hostname.")
    parser.add_argument("--expected-port", type=int, default=5432, help="Approved PostgreSQL port (default 5432).")
    parser.add_argument("--expected-database", help="Exact approved PostgreSQL database name.")
    parser.add_argument("--expected-user", help="Exact approved least-privilege migration role.")
    parser.add_argument("--target-network", choices=("local", "render-internal", "external"), default="local")
    parser.add_argument("--allow-remote", action="store_true", help="Explicitly allow the reviewed non-local destination.")
    parser.add_argument("--apply", action="store_true", help="Write to the destination.")
    parser.add_argument("--confirm-target-db", help="Must exactly equal --expected-database to authorize writes.")
    args = parser.parse_args()
    target_url = resolve_target(args, parser)
    if args.apply and args.confirm_target_db != args.expected_database:
        parser.error("--apply requires --confirm-target-db matching --expected-database")
    if not args.apply and args.confirm_target_db:
        parser.error("--confirm-target-db is only valid with --apply")
    rows, counts = read_source(args.source)
    Base = models_metadata()
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    if set(tables) != set(EXPECTED_TABLES):
        raise RuntimeError("ORM schema does not match the expected 11-table allowlist")
    print("SQLite checks passed; row counts:")
    for name in EXPECTED_TABLES:
        print(f"  {name}: {counts[name]}")
    if not args.apply:
        print("DRY RUN: target was not opened; no writes were made.")
        return 0
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        raise SystemExit("SQLAlchemy is required to apply; destination was not opened.") from None
    engine = create_engine(target_url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    try:
        with engine.begin() as con:
            # Cooperating migration attempts serialize. The destination must also be isolated
            # from app traffic; advisory locks cannot stop unrelated clients from writing.
            con.execute(text("SELECT pg_advisory_xact_lock(731904, 184206)"))
            actual_db = con.execute(text("SELECT current_database()" )).scalar_one()
            if actual_db != args.expected_database:
                raise RuntimeError("Connected database name differs from the approved destination")
            actual_user = con.execute(text("SELECT current_user" )).scalar_one()
            if actual_user != args.expected_user:
                raise RuntimeError("Connected role differs from the approved migration role")
            con.exec_driver_sql("SET LOCAL search_path TO public")
            reject_existing_objects(con)
            Base.metadata.create_all(bind=con)
            for table in Base.metadata.sorted_tables:
                records = [{col.name: convert(row[col.name], col) for col in table.columns if col.name in row}
                           for row in rows[table.name]]
                if records:
                    con.execute(table.insert(), records)
            # Sequence calls are not transactional in PostgreSQL. On a clean target, any
            # sequence created here is covered by transactional DDL; see the runbook for
            # recovery if an existing sequence ever escapes the empty-target guard.
            for table in Base.metadata.sorted_tables:
                keys = list(table.primary_key.columns)
                if len(keys) != 1 or type(keys[0].type).__name__.lower() not in {"integer", "biginteger", "smallinteger"}:
                    continue
                seq = con.execute(text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                                  {"table_name": f"public.{table.name}", "column_name": keys[0].name}).scalar_one_or_none()
                if not seq:
                    raise RuntimeError(f"No owned PostgreSQL sequence found for {table.name}.{keys[0].name}")
                maximum = con.execute(table.select().with_only_columns(keys[0].expression)
                                      .order_by(keys[0].desc()).limit(1)).scalar_one_or_none()
                if maximum is None:
                    con.execute(text("SELECT setval(CAST(:seq AS regclass), 1, false)"), {"seq": seq})
                else:
                    con.execute(text("SELECT setval(CAST(:seq AS regclass), :value, true)"),
                                {"seq": seq, "value": maximum})
        print("Migration transaction committed. Run verify_database_migration.py before cutover.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Migration stopped ({type(exc).__name__}); URL and credentials were not logged.", file=sys.stderr)
        raise SystemExit(1) from None
