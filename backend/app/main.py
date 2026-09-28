"""SecureHelpDesk - application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import attachments, auth, dashboard, logs, tickets, users
from app.seed import bootstrap_admin, seed_lookups

settings = get_settings()
log = logging.getLogger("securehelpdesk")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # later: replace with Alembic migrations
    with SessionLocal() as db:
        seed_lookups(db)
        bootstrap_admin(db, settings.admin_bootstrap_email, settings.admin_bootstrap_name,
                        settings.admin_bootstrap_password)
    if settings.secret_key.startswith("dev-only"):
        log.warning("Using the built-in development SECRET_KEY. Set SECRET_KEY in .env!")
    yield


app = FastAPI(
    title=settings.app_name,
    description="Secure IT Help Desk & Incident Management API",
    version="0.1.0",
    lifespan=lifespan,
    # Interactive docs are handy in development but hidden in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # explicit list, never "*" with credentials
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(_DOC_PATHS):  # Swagger UI needs to load its own scripts
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default 422 echoes the rejected input back - which would include a submitted
    # password. Return only where/why it failed.
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})  # no stack traces


@app.get("/api/health", tags=["System"])
def health():
    return {"status": "ok"}


for r in (auth.router, users.router, tickets.router, attachments.router, logs.router, dashboard.router):
    app.include_router(r)
