# 🎨 Artlife User Authentication API

A production-ready FastAPI backend application connected to PostgreSQL, featuring interactive Swagger documentation, CORS support from all origins, secure BCrypt password hashing, JWT token authentication, and strictly environment-driven database configuration (no hardcoded credentials).

---

## 🌟 Features

* **Account Registration (`POST /register`)**:
  * Fields: `id` (optional, auto-generated if omitted), `firstname`, `lastname`, `phone`, `email`, and `password`.
  * Strong password validation and safe password hashing via BCrypt.
  * Duplicate conflict prevention on `id`, `email`, and `phone` (`409 Conflict`).
* **Email Login (`POST /login`)**:
  * Authenticate using **email** and **password**.
  * Returns a signed JWT Bearer access token and user information.
* **Gallery Product Creation (`POST /gallery/products`)**:
  * Add art products to the gallery with title, description, price, image URL, category, medium, dimensions, stock, and availability.
  * Requires an authenticated admin Bearer token.
* **Interactive Endpoint Documentation**:
  * Swagger UI available at: `http://localhost:8000/docs`
  * ReDoc available at: `http://localhost:8000/redoc`
* **PostgreSQL Connected via `.env`**:
  * Strictly loaded from `.env` via `python-dotenv`.
  * **No hardcoded database URLs** in the codebase.
* **CORS Enabled**:
  * Configured with `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
* **Current User Profile (`GET /me`)**:
  * Authenticated route requiring Bearer JWT token in the `Authorization` header.
* **Database Health Check (`GET /health`)**:
  * Verifies live PostgreSQL connectivity.

---

## 📁 Project Structure

```
Artlife/
├── .env                  # Environment variables (DATABASE_URL, JWT settings)
├── .env.example          # Environment template
├── .gitignore            # Git ignore configuration
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
├── run.py                # Server launcher script
├── test_api.py           # Automated test suite
└── app/
    ├── __init__.py
    ├── config.py         # Loads .env strictly (raises error if DATABASE_URL missing)
    ├── database.py       # SQLAlchemy engine & session dependency
    ├── models.py         # PostgreSQL SQLAlchemy Account model
    ├── schemas.py        # Pydantic models for validation & serialization
    ├── security.py       # BCrypt password hashing & JWT generation/verification
    ├── main.py           # FastAPI app instance, CORS middleware, OpenAPI docs metadata
    └── routers/
        ├── __init__.py
        └── auth.py       # Registration, login, profile, and account list endpoints
```

---

## ⚙️ Configuration (`.env`)

Create or update the `.env` file in the root directory:

```env
# PostgreSQL Database URL (No hardcoded credentials in Python code)
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/artlife_db

# Security & JWT
JWT_SECRET_KEY=artlife-super-secure-secret-key-replace-in-production-2026
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Server
HOST=0.0.0.0
PORT=8000
ENVIRONMENT=development
```

> **Note:** If `DATABASE_URL` is omitted from `.env`, the application will immediately refuse to start with an explicit descriptive error.

---

## 🚀 Running the Application

### Option 1: Using the Runner Script
```bash
python run.py
```

### Option 2: Using Uvicorn Directly
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server will be running at:
* **Base URL**: `http://localhost:8000`
* **Interactive Docs (Swagger UI)**: `http://localhost:8000/docs`
* **Alternative Docs (ReDoc)**: `http://localhost:8000/redoc`

---

## 📡 API Endpoints

### 1. Create Account
* **Endpoint**: `POST /register` *(or `POST /auth/register`)*
* **Status Code**: `201 Created`
* **Headers**: `Content-Type: application/json`

**Request Body (with optional custom ID):**
```json
{
  "id": 101,
  "firstname": "John",
  "lastname": "Doe",
  "phone": "+1234567890",
  "email": "john.doe@example.com",
  "password": "SecurePassword123!"
}
```

**Request Body (omitting `id` for auto-generated sequence):**
```json
{
  "firstname": "Jane",
  "lastname": "Smith",
  "phone": "+1987654321",
  "email": "jane.smith@example.com",
  "password": "SecurePassword123!"
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "firstname": "Jane",
  "lastname": "Smith",
  "phone": "+1987654321",
  "email": "jane.smith@example.com",
  "role": "user",
  "created_at": "2026-10-13T16:04:34.375648+02:00",
  "updated_at": "2026-10-13T16:04:34.375648+02:00"
}
```

---

### 2. Login (Email + Password)
* **Endpoint**: `POST /login` *(or `POST /auth/login`)*
* **Status Code**: `200 OK`
* **Headers**: `Content-Type: application/json`

**Login using Email:**
```json
{
  "email": "john.doe@example.com",
  "password": "SecurePassword123!"
}
```

**Response (`200 OK`):**
```json
{
  "message": "Login successful",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 101,
    "firstname": "John",
    "lastname": "Doe",
    "phone": "+1234567890",
    "email": "john.doe@example.com",
    "role": "user",
    "created_at": "2026-10-13T16:04:33.969660+02:00",
    "updated_at": "2026-10-13T16:04:33.969660+02:00"
  }
}
```

---

### 3. Current User Profile
* **Endpoint**: `GET /me` *(or `GET /auth/me`)*
* **Status Code**: `200 OK`
* **Headers**: `Authorization: Bearer <your_access_token>`

---

### 4. Add Gallery Product
* **Endpoint**: `POST /gallery/products`
* **Status Code**: `201 Created`
* **Headers**:
  * `Content-Type: application/json`
  * `Authorization: Bearer <admin_access_token>`

**Request Body:**
```json
{
  "title": "Sunset Over Table Mountain",
  "description": "Original acrylic painting inspired by Cape Town sunsets.",
  "price": "1250.00",
  "image_url": "https://example.com/art/sunset.jpg",
  "category": "Painting",
  "medium": "Acrylic on canvas",
  "dimensions": "60cm x 90cm",
  "stock_quantity": 1,
  "is_available": true
}
```

**Response (`201 Created`):**
```json
{
  "id": 1,
  "title": "Sunset Over Table Mountain",
  "description": "Original acrylic painting inspired by Cape Town sunsets.",
  "price": "1250.00",
  "image_url": "https://example.com/art/sunset.jpg",
  "category": "Painting",
  "medium": "Acrylic on canvas",
  "dimensions": "60cm x 90cm",
  "stock_quantity": 1,
  "is_available": true,
  "created_by_id": 1,
  "created_at": "2026-10-19T14:00:00.000000+02:00",
  "updated_at": "2026-10-19T14:00:00.000000+02:00"
}
```

---

### 5. Database Health Check
* **Endpoint**: `GET /health`
* **Status Code**: `200 OK`

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "dialect": "postgresql"
}
```

---

## 🧪 Testing

Run the included verification suite to test database connectivity, table initialization, registration, logins, CORS headers, and error handling:

```bash
python test_api.py
```
"# Artlife_api" 
