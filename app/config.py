import os
from pathlib import Path
# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Explicit path to .env file
ENV_PATH = BASE_DIR / ".env"

# Load environment variables from .env file (supports python-dotenv or built-in fallback)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_PATH)
except ModuleNotFoundError:
    # Built-in zero-dependency fallback to parse .env if python-dotenv is not installed
    if ENV_PATH.is_file():
        with open(ENV_PATH, "r", encoding="utf-8") as _env_file:
            for _line in _env_file:
                _line = _line.strip()
                if not _line or _line.startswith("#") or "=" not in _line:
                    continue
                _key, _val = _line.split("=", 1)
                _key = _key.strip()
                _val = _val.strip()
                if (_val.startswith('"') and _val.endswith('"')) or (_val.startswith("'") and _val.endswith("'")):
                    _val = _val[1:-1]
                if _key and _key not in os.environ:
                    os.environ[_key] = _val


# Fetch DATABASE_URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

# Strict check: No hardcoded database URL fallback in code
if not DATABASE_URL or not DATABASE_URL.strip():
    raise RuntimeError(
        f"DATABASE_URL is not set in environment or in '{ENV_PATH}'. "
        "Please provide a valid DATABASE_URL in the .env file (e.g. postgresql+psycopg2://user:password@localhost:5432/dbname)."
    )

def _normalize_database_url(url: str) -> str:
    import re
    from urllib.parse import quote_plus
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Encode raw password if it contains special characters (like /, ?, &, etc.)
    match = re.match(r"^(?P<scheme>[a-zA-Z0-9+]+://)(?P<user>[^:]+):(?P<password>.+)@(?P<host>.+)$", url)
    if match:
        scheme = match.group("scheme")
        user = match.group("user").strip()
        pwd = match.group("password").strip()
        host = match.group("host").strip()
        if any(c in pwd for c in ["/", " ", "?", "#", "@"]):
            pwd = quote_plus(pwd)
        url = f"{scheme}{user}:{pwd}@{host}"
    return url


DATABASE_URL = _normalize_database_url(DATABASE_URL)

# Security and JWT configurations
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "artlife-default-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Server configurations
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
