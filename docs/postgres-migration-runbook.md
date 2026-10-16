# SQLite → PostgreSQL migration runbook

This runbook prepares a controlled migration of `pasajes_pre_migracion_backup.db` into a **new, empty, isolated PostgreSQL database**. It does not authorize connecting to Render or changing the production application. Do not use the production database as the migration target.

## Current safeguards in the scripts

- The SQLite file is opened read-only and checked with `integrity_check`, exact table allowlist and `foreign_key_check`.
- The PostgreSQL URL is read only from `MIGRATION_TARGET_URL`; it is never a command-line argument or printed. Exact hostname, port (default 5432), database and migration role must match `--expected-host`, `--expected-port`, `--expected-database` and `--expected-user`; the connected database and role are also checked.
- Remote use requires `--allow-remote`. `--target-network external` also requires `sslmode=require` or stronger. Use `render-internal` only for a service in the database's same Render region.
- Apply requires `--apply --confirm-target-db <same-db-name>`. The importer checks `current_database()`, obtains a transaction-scoped advisory lock and refuses user relations anywhere outside system schemas. It has no `DROP`, `TRUNCATE`, `DELETE`, upsert or overwrite path.
- Schema creation, explicit-ID inserts and sequence positioning run in one PostgreSQL transaction. `Base.metadata.sorted_tables` inserts parent tables before dependent tables. PostgreSQL rolls back the DDL and rows on failure. Sequence advancement (`setval`) is not transactional; a sequence value can survive rollback if a pre-existing sequence were ever touched. The empty-target guard rejects sequences before import, and a sequence created by this transaction is removed with rolled-back DDL. Never bypass that guard or retry into a target with leftover objects.
- The verifier is read-only and compares SQLite directly with PostgreSQL table by table: columns, normalized type names, primary key order, UNIQUE constraints, explicit index key/include columns and uniqueness, nullability, defaults, foreign keys/actions, counts and all values. It also checks purchase/payment totals by status, PostgreSQL FK integrity, and sequence state. Index names are ignored because the generated names differ between engines; their indexed columns and uniqueness are compared.
- Expression indexes are conservatively represented from each engine's catalog SQL and may be reported as different even when semantically equivalent. The current application schema uses column indexes, not expression indexes; any such report requires manual review and must not be treated as a pass.

## 1. Local preparation and no-network checks (PowerShell)

Run from the repository root. These commands do not open PostgreSQL connections:

```powershell
git status --short --branch
Get-FileHash .\pasajes_pre_migracion_backup.db -Algorithm SHA256
& .\.venv_migracion312_reparado\Scripts\python.exe -m py_compile .\scripts\migrate_sqlite_to_postgres.py .\scripts\verify_database_migration.py .\tests\test_verify_database_migration.py
& .\.venv_migracion312_reparado\Scripts\python.exe -m scripts.migrate_sqlite_to_postgres --help
& .\.venv_migracion312_reparado\Scripts\python.exe -m scripts.verify_database_migration --help
& .\.venv_migracion312_reparado\Scripts\python.exe -m unittest discover -s tests -v
```

Dry-run the importer against each SQLite file. These commands validate integrity, table allowlist and foreign keys and never open PostgreSQL:

```powershell
& .\.venv_migracion312_reparado\Scripts\python.exe -m scripts.migrate_sqlite_to_postgres --source .\pasajes.db
& .\.venv_migracion312_reparado\Scripts\python.exe -m scripts.migrate_sqlite_to_postgres --source .\pasajes_pre_migracion_backup.db
```

If `py_compile` cannot write under `__pycache__`, use this in-memory syntax check without changing permissions:

```powershell
& .\.venv_migracion312_reparado\Scripts\python.exe -c "from pathlib import Path; files=['scripts/migrate_sqlite_to_postgres.py','scripts/verify_database_migration.py','tests/test_verify_database_migration.py']; [compile(Path(f).read_text(encoding='utf-8'), f, 'exec') for f in files]; print('syntax ok')"
```

If `.venv_migracion312_reparado\Scripts\python.exe` itself cannot start because its configured base interpreter is missing, stop here and repair that local Python installation through the normal approved setup. Neither the in-memory fallback nor the test suite can run without a functioning interpreter; do not alter permissions or substitute an unreviewed runtime.

The backup and migration virtual environment are excluded from Git. No local PostgreSQL installation is required.

## 2. Prepare an isolated Render runner (future, requires separate authorization)

The project currently has no `render.yaml` or migration runner service. `app/main.py` is the web application and runs `create_all` plus optional seed logic at startup. Do not repurpose or redeploy the production web service for the migration.

After review and authorization, make the migration code available in a dedicated branch/revision and create a **separate temporary private/background service** in Oregon from that revision. Configure only that temporary service with:

1. `MIGRATION_TARGET_URL` as a Render secret environment variable, preferably the internal URL for a new, empty migration database in Oregon. Never copy it to terminal history, arguments or logs. If external access is selected, use the full external host with `sslmode=require`, restrict the database IP allow list to the runner's known egress IP, and restore the previous allow list afterward.
2. A Render Secret File named `pasajes_pre_migracion_backup.db` containing the verified 155,648-byte SQLite backup. At runtime the source path is `/etc/secrets/pasajes_pre_migracion_backup.db`. Render documents a 1 MB combined Secret Files limit. Do not place the database in Git, a public URL, a Docker image/build context, or the production service. For Docker services, Render warns secret files can enter the build context; the temporary runner should use a non-Docker runtime or explicitly keep the file out of the image.
3. No public inbound route, no production `DATABASE_URL`, and no production environment group. The runner's command should be a harmless idle command so only the explicit one-off job performs work.

Render one-off jobs use an existing service's latest successful build and its environment snapshot, then are deprovisioned when the command exits. Therefore a separate temporary runner is necessary to keep its migration URL and source file away from the production service. The one-off job incurs the runner's compute charge. Confirm plan/cost and the exact database hostname/name from the Render dashboard before proceeding.

## 3. Future controlled run sequence (do not execute until approved)

In the Render dashboard, open **only the temporary runner** and create a one-off job with each command below. No database URL is part of either command. Replace `<approved-host>`, `<approved-database>` and `<migration-role>` with the reviewed values from the temporary target's connection details, not guessed values. The expected port defaults to 5432; specify `--expected-port` if the approved endpoint uses a different port.

Dry-run (no PostgreSQL connection):

```text
python -m scripts.migrate_sqlite_to_postgres --source /etc/secrets/pasajes_pre_migracion_backup.db --expected-host <approved-host> --expected-database <approved-database> --expected-user <migration-role> --target-network render-internal --allow-remote
```

Before apply, take/confirm a restorable target backup, confirm the target is the new empty migration database, stop any writers to it, and verify the job is still attached to the temporary runner. Then, as a separate manually reviewed job:

```text
python -m scripts.migrate_sqlite_to_postgres --source /etc/secrets/pasajes_pre_migracion_backup.db --expected-host <approved-host> --expected-database <approved-database> --expected-user <migration-role> --target-network render-internal --allow-remote --apply --confirm-target-db <approved-database>
```

After a successful exit, run the read-only verifier as another job on that runner:

```text
python -m scripts.verify_database_migration --source /etc/secrets/pasajes_pre_migracion_backup.db --expected-host <approved-host> --expected-database <approved-database> --expected-user <migration-role> --target-network render-internal --allow-remote
```

Do not change production `DATABASE_URL` unless the verifier exits successfully and its logged report has all eleven table counts equal, no row/FK/sequence differences, and matching purchase/payment totals by status. This runbook does not authorize that production cutover.

If the Render endpoint supplied is an external URL instead, use `--target-network external` in both scripts and ensure its URL query has `sslmode=require` (or stronger). Do not broaden the allow list to `0.0.0.0/0` to make a connection work.

## 4. Recovery

- **Dry run fails:** it did not open PostgreSQL. Correct only the source path/schema or the reviewed host/database inputs, then rerun the dry run.
- **Apply fails before commit:** SQLAlchemy rolls back inserted rows and table DDL. The script does not delete or replace existing data. Confirm the isolated target has no user relations before retrying. The advisory lock coordinates only executions of this script; keep unrelated writers stopped.
- **Apply succeeds but verifier fails:** do not point the app at the target. Preserve the SQLite source and backup. Inspect the verifier's table/row/FK/aggregate/sequence diagnostics; treat the target as failed and do not rerun import over it. Recovery should use a newly provisioned empty migration database after review, because the importer intentionally refuses existing objects.
- **Sequence state after rollback:** PostgreSQL sequence calls are not rolled back. The script's empty-destination guard means no pre-existing sequence should be changed; transactional DDL removes sequences created in the failed transaction. If any sequence or user relation remains, stop and use an administrator-reviewed recovery on the isolated target; do not add a destructive cleanup option to this importer.
- **Runner cleanup:** after preserving the non-secret verification report, remove the temporary runner's secret file and migration URL, then delete/suspend the temporary runner through the Render dashboard. Do not remove either SQLite file.

## 5. Still needed before a real migration

- Review the local diff and approve publishing/deploying a dedicated migration revision and creating a temporary Render runner.
- Confirm the exact new target database, region, hostname, database name, target backup/recovery plan, runner plan/cost, and whether the internal endpoint is available.
- Supply the migration URL only through the temporary runner's protected environment setting and the SQLite file only as its Secret File.
- Authorize the one-off dry run, then separately authorize the import and verification. Production cutover needs its own explicit approval after a successful verification report.
