from contextlib import asynccontextmanager

import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import inspect, text

from .database import Base, SessionLocal, engine
from .routers import admin, public, tracking, validator
from .seed import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # Migración mínima y no destructiva para instalaciones SQLite ya existentes.
    inspector = inspect(engine)
    if "purchases" in inspector.get_table_names() and "company_id" not in {column["name"] for column in inspector.get_columns("purchases")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE purchases ADD COLUMN company_id INTEGER"))
    with SessionLocal() as db:
        seed_database(db)
    yield


app = FastAPI(title="Pasajes Sabana", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32), https_only=False, same_site="lax")
app.state.templates = Jinja2Templates(directory="app/templates")
app.state.maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(public.router)
app.include_router(validator.router)
app.include_router(admin.router)
app.include_router(tracking.router)

@app.exception_handler(Exception)
async def controlled_error(request: Request, exc: Exception):
    # Los detalles técnicos se registran en el servidor; la interfaz no recibe tracebacks.
    import logging
    logging.exception("Error no controlado en %s", request.url.path, exc_info=exc)
    return HTMLResponse("<h1>Error temporal</h1><p>No fue posible completar la operación. Inténtalo de nuevo.</p>", status_code=500)
