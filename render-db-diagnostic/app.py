import hmac
import os

import psycopg
from fastapi import FastAPI, Header, HTTPException, Response

app = FastAPI(title="Temporary PostgreSQL connectivity diagnostic")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/diagnostic")
def diagnostic(response: Response, authorization: str | None = Header(default=None)):
    expected_token = os.getenv("DIAGNOSTIC_TOKEN", "")
    database_url = os.getenv("DIAGNOSTIC_DATABASE_URL", "")
    if not expected_token or not database_url:
        raise HTTPException(status_code=503, detail="Diagnostic is not configured")

    supplied_token = authorization.removeprefix("Bearer ") if authorization else ""
    if not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        with psycopg.connect(database_url, connect_timeout=8) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            row = connection.execute(
                """
                SELECT current_database(), current_user,
                       current_setting('transaction_read_only'),
                       (SELECT count(*) FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_type = 'BASE TABLE')
                """
            ).fetchone()
    except Exception:
        # Deliberately omit exception details: database errors may include connection data.
        raise HTTPException(status_code=503, detail="Database diagnostic failed") from None

    response.headers["Cache-Control"] = "no-store"
    return {
        "connected": True,
        "current_database": row[0],
        "current_user": row[1],
        "transaction_read_only": row[2],
        "public_table_count": row[3],
    }
