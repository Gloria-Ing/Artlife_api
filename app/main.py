from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.routers import auth, products, cart

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def ensure_account_role_column() -> None:
    """
    Add the role column for existing databases created before admin accounts existed.
    """
    inspector = inspect(engine)
    if not inspector.has_table("accounts"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "role" in existing_columns:
        return

    dialect = engine.dialect.name
    ddl = "ALTER TABLE accounts ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
    if dialect == "postgresql":
        ddl = "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'"

    with engine.begin() as connection:
        connection.execute(text(ddl))


def remove_account_username_column() -> None:
    """
    Remove the old username column from existing accounts tables.
    """
    inspector = inspect(engine)
    if not inspector.has_table("accounts"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("accounts")}
    if "username" not in existing_columns:
        return

    dialect = engine.dialect.name
    ddl = "ALTER TABLE accounts DROP COLUMN username"
    if dialect == "postgresql":
        ddl = "ALTER TABLE accounts DROP COLUMN IF EXISTS username CASCADE"
    elif dialect == "sqlite":
        ddl = "ALTER TABLE accounts DROP COLUMN username"

    with engine.begin() as connection:
        connection.execute(text(ddl))


def ensure_account_schema() -> None:
    """
    Keep existing accounts tables aligned with the current Account model.
    """
    ensure_account_role_column()
    remove_account_username_column()


def ensure_gallery_product_schema() -> None:
    """
    Add gallery product commerce columns for databases created before price/images existed.
    """
    inspector = inspect(engine)
    if not inspector.has_table("gallery_products"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("gallery_products")}
    statements = []
    dialect = engine.dialect.name

    if "price" not in existing_columns:
        if dialect == "postgresql":
            statements.append("ALTER TABLE gallery_products ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2)")
        else:
            statements.append("ALTER TABLE gallery_products ADD COLUMN price NUMERIC(10, 2)")

    if "image_url" not in existing_columns:
        if dialect == "postgresql":
            statements.append("ALTER TABLE gallery_products ADD COLUMN IF NOT EXISTS image_url VARCHAR(500)")
        else:
            statements.append("ALTER TABLE gallery_products ADD COLUMN image_url VARCHAR(500)")

    if "image_data" not in existing_columns:
        if dialect == "postgresql":
            statements.append("ALTER TABLE gallery_products ADD COLUMN IF NOT EXISTS image_data BYTEA")
        else:
            statements.append("ALTER TABLE gallery_products ADD COLUMN image_data BLOB")

    if "image_content_type" not in existing_columns:
        if dialect == "postgresql":
            statements.append("ALTER TABLE gallery_products ADD COLUMN IF NOT EXISTS image_content_type VARCHAR(100)")
        else:
            statements.append("ALTER TABLE gallery_products ADD COLUMN image_content_type VARCHAR(100)")

    if not statements:
        return

    with engine.begin() as connection:
        for ddl in statements:
            connection.execute(text(ddl))


def ensure_database_schema() -> None:
    """
    Keep existing tables aligned with the current models.
    """
    ensure_account_schema()
    ensure_gallery_product_schema()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Ensures database tables are created automatically on startup.
    """
    # Create tables in PostgreSQL if they do not exist
    Base.metadata.create_all(bind=engine)
    ensure_database_schema()
    yield


app = FastAPI(
    title="Artlife User & Authentication API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============================================================
# CORS Middleware: Enabled from all origins
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# ============================================================
# Include Routers
# ============================================================
# Root paths: /register, /admin/register, /login, /me, /accounts, /gallery/products
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)

# Prefix aliases: /auth/register, /auth/admin/register, /auth/login, /auth/me
app.include_router(auth.router, prefix="/auth", tags=["Authentication & Accounts (Alias)"])


# ============================================================
# General & Health Endpoints
# ============================================================
@app.get(
    "/",
    tags=["General"],
    summary="Root Welcome & Service Information",
    description="Returns welcome information and links to interactive API documentation.",
)
def root():
    return {
        "service": "Artlife User & Authentication API",
        "status": "online",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "endpoints": {
            "register": "POST /register (or POST /auth/register)",
            "admin_register": "POST /admin/register (or POST /auth/admin/register)",
            "login": "POST /login (or POST /auth/login)",
            "profile": "GET /me (requires Bearer token)",
            "accounts": "GET /accounts",
            "gallery_products": "GET /gallery/products",
            "create_product": "POST /gallery/products (requires admin Bearer token)",
            "health": "GET /health",
            "cart": "GET /cart (requires Bearer token)",
            "cart_add": "POST /cart/items (requires Bearer token)",
            "cart_update": "PUT /cart/items/{item_id} (requires Bearer token)",
            "cart_remove_item": "DELETE /cart/items/{item_id} (requires Bearer token)",
            "cart_clear": "DELETE /cart (requires Bearer token)",
        },
    }


@app.get(
    "/health",
    tags=["General"],
    summary="Health & PostgreSQL Database Check",
    description="Checks the health of the application and validates connectivity to PostgreSQL.",
    status_code=status.HTTP_200_OK,
)
def health_check(db: Session = Depends(get_db)):
    try:
        # Execute test query in PostgreSQL
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "dialect": engine.dialect.name,
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc),
        }
