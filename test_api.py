import sys
from fastapi.testclient import TestClient
from app.main import app
from app.main import ensure_account_schema
from app.database import engine, Base

def run_tests():
    print("==================================================")
    print(" Running Automated Verification Suite for Artlife ")
    print("==================================================")

    # Initialize tables
    Base.metadata.create_all(bind=engine)
    ensure_account_schema()
    client = TestClient(app)

    # 1. Health check
    print("\n[1] Testing /health endpoint...")
    res = client.get("/health")
    print(f"Status: {res.status_code}, Body: {res.json()}")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    assert res.json().get("database") == "connected", "Database is not connected"
    print("-> /health passed successfully!")

    # 2. CORS preflight check
    print("\n[2] Testing CORS headers from origin...")
    res = client.options(
        "/register",
        headers={
            "Origin": "http://example-frontend.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    print(f"CORS status: {res.status_code}, Headers: {dict(res.headers)}")
    assert "access-control-allow-origin" in res.headers, "CORS header missing"
    print("-> CORS check passed successfully!")

    # 3. Reject weak password
    import time
    ts = int(time.time())
    weak_password_account = {
        "firstname": "Weak",
        "lastname": "Password",
        "phone": f"+111000{ts % 10000}",
        "email": f"weak_{ts}@example.com",
        "password": "password",
    }
    print("\n[3] Testing weak password rejection...")
    res = client.post("/register", json=weak_password_account)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 422, f"Expected 422 for weak password, got {res.status_code}"
    print("-> Weak password correctly rejected!")

    # 4. Create Account with explicit ID
    account_data_1 = {
        "id": ts % 100000 + 10000,
        "firstname": "Alice",
        "lastname": "Wonder",
        "phone": f"+123456{ts % 10000}",
        "email": f"alice_{ts}@example.com",
        "password": "SuperSecretPassword123!",
    }
    print(f"\n[4] Testing account creation with explicit ID ({account_data_1['id']})...")
    res = client.post("/register", json=account_data_1)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create account: {res.text}"
    created_user_1 = res.json()
    assert created_user_1["id"] == account_data_1["id"], "ID mismatch"
    assert "username" not in created_user_1, "Username should not be returned"
    assert created_user_1["role"] == "user", "Regular account should have user role"
    assert "password" not in created_user_1, "Plain password exposed in response!"
    assert "password_hash" not in created_user_1, "Password hash exposed in response!"
    print("-> Explicit ID account creation passed successfully!")

    # 5. Create Admin Account
    admin_data = {
        "firstname": "Artlife",
        "lastname": "Admin",
        "phone": f"+555000{ts % 10000}",
        "email": f"admin_{ts}@example.com",
        "password": "AdminSecretPassword123!",
    }
    print("\n[5] Testing admin account creation...")
    res = client.post("/admin/register", json=admin_data)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create admin account: {res.text}"
    created_admin = res.json()
    assert "username" not in created_admin, "Username should not be returned"
    assert created_admin["role"] == "admin", "Admin account should have admin role"
    assert "password" not in created_admin, "Plain password exposed in response!"
    assert "password_hash" not in created_admin, "Password hash exposed in response!"
    print("-> Admin account creation passed successfully!")

    # 6. Create Account with auto-generated ID (omitting id)
    account_data_2 = {
        "firstname": "Bob",
        "lastname": "Builder",
        "phone": f"+987654{ts % 10000}",
        "email": f"bob_{ts}@example.com",
        "passord": "BobSecurePass456!",  # Testing typo alias support as well
    }
    print(f"\n[6] Testing account creation with auto-generated ID (omitted id)...")
    res = client.post("/register", json=account_data_2)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create account with auto ID: {res.text}"
    created_user_2 = res.json()
    assert created_user_2["id"] is not None and isinstance(created_user_2["id"], int)
    print(f"-> Auto-generated ID assigned: {created_user_2['id']}")

    # 7. Login using Email
    print(f"\n[7] Testing login using email '{account_data_1['email']}'...")
    login_payload_email = {
        "email": account_data_1["email"],
        "password": account_data_1["password"],
    }
    res = client.post("/login", json=login_payload_email)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Email login failed: {res.text}"
    login_resp = res.json()
    assert "access_token" in login_resp, "Token missing in login response"
    assert login_resp["user"]["email"] == account_data_1["email"]
    assert "username" not in login_resp["user"], "Username should not be returned"
    token = login_resp["access_token"]
    print("-> Login via email successful!")

    # 8. Login using Admin Email
    print(f"\n[8] Testing admin login using email '{admin_data['email']}'...")
    admin_login_payload = {
        "email": admin_data["email"],
        "password": admin_data["password"],
    }
    res = client.post("/login", json=admin_login_payload)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Admin email login failed: {res.text}"
    admin_token = res.json()["access_token"]
    print("-> Admin login via email successful!")

    # 9. Login using Phone should no longer be supported
    print(f"\n[9] Testing phone login is rejected...")
    login_payload_phone = {
        "phone": account_data_1["phone"],
        "password": account_data_1["password"],
    }
    res = client.post("/login", json=login_payload_phone)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 422, f"Expected 422 for phone login, got {res.status_code}"
    print("-> Phone login correctly rejected!")

    # 10. Login with invalid password
    print("\n[10] Testing login with invalid password...")
    bad_login = {
        "email": account_data_1["email"],
        "password": "WrongPassword!",
    }
    res = client.post("/login", json=bad_login)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 401, f"Expected 401 for wrong password, got {res.status_code}"
    print("-> Invalid password correctly rejected with 401!")

    # 11. Test Protected Profile Route with JWT Token
    print("\n[11] Testing protected /me route with JWT token...")
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Protected route failed: {res.text}"
    assert res.json()["email"] == account_data_1["email"]
    assert "username" not in res.json(), "Username should not be returned"
    print("-> Protected /me route passed successfully!")

    # 12. Test Admin Product Creation
    product_payload = {
        "title": f"Sunset Over Table Mountain {ts}",
        "description": "Original acrylic painting inspired by Cape Town sunsets.",
        "price": "1250.00",
        "image_url": "https://example.com/art/sunset.jpg",
        "category": "Painting",
        "medium": "Acrylic on canvas",
        "dimensions": "60cm x 90cm",
        "stock_quantity": 1,
        "is_available": True,
    }
    print("\n[12] Testing admin-only gallery product creation...")
    res = client.post("/gallery/products", json=product_payload)
    print(f"No-token status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 401, f"Expected 401 without token, got {res.status_code}"

    res = client.post(
        "/gallery/products",
        json=product_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"User-token status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 403, f"Expected 403 with regular user token, got {res.status_code}"

    res = client.post(
        "/gallery/products",
        json=product_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    print(f"Admin-token status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Admin product creation failed: {res.text}"
    created_product = res.json()
    assert created_product["title"] == product_payload["title"]
    assert created_product["created_by_id"] == created_admin["id"]
    assert created_product["is_available"] is True
    print("-> Admin-only gallery product creation passed successfully!")

    # 13. Test duplicate registration prevention
    print("\n[13] Testing duplicate registration conflict...")
    res = client.post("/register", json=account_data_1)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 409, f"Expected 409 for duplicate account, got {res.status_code}"
    print("-> Duplicate prevention passed successfully!")

    # 14. Swagger Docs / OpenAPI JSON check
    print("\n[14] Testing /openapi.json and documentation availability...")
    res = client.get("/openapi.json")
    assert res.status_code == 200, "OpenAPI json failed"
    openapi = res.json()
    assert "/register" in openapi["paths"]
    assert "/admin/register" in openapi["paths"]
    assert "/login" in openapi["paths"]
    assert "/gallery/products" in openapi["paths"]
    login_schema = openapi["components"]["schemas"]["LoginRequest"]
    account_create_schema = openapi["components"]["schemas"]["AccountCreate"]
    product_create_schema = openapi["components"]["schemas"]["ProductCreate"]
    assert "email" in login_schema["properties"]
    assert "username" not in login_schema["properties"]
    assert "username" not in account_create_schema["properties"]
    assert "price" in product_create_schema["properties"]
    print("-> Documentation paths present in OpenAPI schema!")

    print("\n==================================================")
    print(" ALL 14 TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
