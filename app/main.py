from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Ensures database tables are created automatically on startup.
    """
    # Create tables in PostgreSQL if they do not exist
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Artlife User & Authentication API",
    description="""
# 🎨 Artlife Authentication & Account Service

A high-performance FastAPI service connected to PostgreSQL with comprehensive endpoint documentation and CORS enabled.

---

### 🚀 Key Features:
* **Account Creation**: Register accounts with `id`, `firstname`, `lastname`, `username`, `phone`, `email`, and `password`.
* **Flexible Login**: Authenticate with either **Username** OR **Phone Number** along with password.
* **PostgreSQL Integration**: Seamless connection managed via `.env` with no hardcoded credentials.
* **CORS Support**: Configured to accept requests from all origins (`*`).
* **Secure BCrypt Hashing**: Passwords stored as industry-standard salted BCrypt hashes.
* **JWT Authentication**: Fast and stateless Bearer tokens for authenticated endpoints.

---

### 📖 Documentation Links:
* **Interactive Swagger UI**: [/docs](/docs)
* **ReDoc Documentation**: [/redoc](/redoc)
* **OpenAPI Specification**: [/openapi.json](/openapi.json)
    """,
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

# ============================================================
# Include Routers
# ============================================================
# Root paths: /register, /login, /me, /accounts
app.include_router(auth.router)

# Prefix aliases: /auth/register, /auth/login, /auth/me
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
            "login": "POST /login (or POST /auth/login)",
            "profile": "GET /me (requires Bearer token)",
            "accounts": "GET /accounts",
            "health": "GET /health",
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
