import hmac
import os

import psycopg
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/")
def health():
    return {"service": "database-diagnostic", "status": "ready"}


@app.get("/diagnostic")
def diagnostic(x_diagnostic_token: str = Header(default="")):
    expected = os.environ.get("DIAGNOSTIC_TOKEN", "")
    if not expected or not hmac.compare_digest(x_diagnostic_token, expected):
        raise HTTPException(status_code=404, detail="Not found")

    target = os.environ.get("MIGRATION_TARGET_URL", "")
    if not target:
        raise HTTPException(status_code=503, detail="Diagnostic not configured")

    try:
        with psycopg.connect(target, connect_timeout=10, autocommit=True) as conn:
            conn.execute("BEGIN READ ONLY")
            try:
                row = conn.execute(
                    """
                    SELECT current_database(),
                           current_user,
                           current_setting('transaction_read_only')
                    """
                ).fetchone()
                table_count = conn.execute(
                    """
                    SELECT count(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                ).fetchone()[0]
                result = {
                    "database": row[0],
                    "user": row[1],
                    "read_only": row[2],
                    "public_tables": table_count,
                }
            finally:
                conn.execute("ROLLBACK")
        return result
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database diagnostic failed; inspect server configuration privately",
        )
