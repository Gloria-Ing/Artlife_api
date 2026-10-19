import sys
from fastapi.testclient import TestClient
from app.main import app
from app.main import ensure_account_role_column
from app.database import engine, Base

def run_tests():
    print("==================================================")
    print(" Running Automated Verification Suite for Artlife ")
    print("==================================================")

    # Initialize tables
    Base.metadata.create_all(bind=engine)
    ensure_account_role_column()
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

    # 3. Create Account with explicit ID
    import time
    ts = int(time.time())
    account_data_1 = {
        "id": ts % 100000 + 10000,
        "firstname": "Alice",
        "lastname": "Wonder",
        "username": f"alice_{ts}",
        "phone": f"+123456{ts % 10000}",
        "email": f"alice_{ts}@example.com",
        "password": "SuperSecretPassword123!",
    }
    print(f"\n[3] Testing account creation with explicit ID ({account_data_1['id']})...")
    res = client.post("/register", json=account_data_1)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create account: {res.text}"
    created_user_1 = res.json()
    assert created_user_1["id"] == account_data_1["id"], "ID mismatch"
    assert created_user_1["username"] == account_data_1["username"]
    assert created_user_1["role"] == "user", "Regular account should have user role"
    assert "password" not in created_user_1, "Plain password exposed in response!"
    assert "password_hash" not in created_user_1, "Password hash exposed in response!"
    print("-> Explicit ID account creation passed successfully!")

    # 4. Create Admin Account
    admin_data = {
        "firstname": "Artlife",
        "lastname": "Admin",
        "username": f"admin_{ts}",
        "phone": f"+555000{ts % 10000}",
        "email": f"admin_{ts}@example.com",
        "password": "AdminSecretPassword123!",
    }
    print("\n[4] Testing admin account creation...")
    res = client.post("/admin/register", json=admin_data)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create admin account: {res.text}"
    created_admin = res.json()
    assert created_admin["role"] == "admin", "Admin account should have admin role"
    assert "password" not in created_admin, "Plain password exposed in response!"
    assert "password_hash" not in created_admin, "Password hash exposed in response!"
    print("-> Admin account creation passed successfully!")

    # 5. Create Account with auto-generated ID (omitting id)
    account_data_2 = {
        "firstname": "Bob",
        "lastname": "Builder",
        "username": f"bob_{ts}",
        "phone": f"+987654{ts % 10000}",
        "email": f"bob_{ts}@example.com",
        "passord": "BobSecurePass456!",  # Testing typo alias support as well
    }
    print(f"\n[5] Testing account creation with auto-generated ID (omitted id)...")
    res = client.post("/register", json=account_data_2)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201, f"Failed to create account with auto ID: {res.text}"
    created_user_2 = res.json()
    assert created_user_2["id"] is not None and isinstance(created_user_2["id"], int)
    print(f"-> Auto-generated ID assigned: {created_user_2['id']}")

    # 6. Login using Username
    print(f"\n[6] Testing login using username '{account_data_1['username']}'...")
    login_payload_username = {
        "username_or_phone": account_data_1["username"],
        "password": account_data_1["password"],
    }
    res = client.post("/login", json=login_payload_username)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Username login failed: {res.text}"
    login_resp = res.json()
    assert "access_token" in login_resp, "Token missing in login response"
    token = login_resp["access_token"]
    print("-> Login via username successful!")

    # 7. Login using Phone
    print(f"\n[7] Testing login using phone '{account_data_1['phone']}'...")
    login_payload_phone = {
        "username_or_phone": account_data_1["phone"],
        "password": account_data_1["password"],
    }
    res = client.post("/login", json=login_payload_phone)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Phone login failed: {res.text}"
    print("-> Login via phone successful!")

    # 8. Login with invalid password
    print("\n[8] Testing login with invalid password...")
    bad_login = {
        "username_or_phone": account_data_1["username"],
        "password": "WrongPassword!",
    }
    res = client.post("/login", json=bad_login)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 401, f"Expected 401 for wrong password, got {res.status_code}"
    print("-> Invalid password correctly rejected with 401!")

    # 9. Test Protected Profile Route with JWT Token
    print("\n[9] Testing protected /me route with JWT token...")
    res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200, f"Protected route failed: {res.text}"
    assert res.json()["username"] == account_data_1["username"]
    print("-> Protected /me route passed successfully!")

    # 10. Test duplicate registration prevention
    print("\n[10] Testing duplicate registration conflict...")
    res = client.post("/register", json=account_data_1)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 409, f"Expected 409 for duplicate username, got {res.status_code}"
    print("-> Duplicate prevention passed successfully!")

    # 11. Swagger Docs / OpenAPI JSON check
    print("\n[11] Testing /openapi.json and documentation availability...")
    res = client.get("/openapi.json")
    assert res.status_code == 200, "OpenAPI json failed"
    openapi = res.json()
    assert "/register" in openapi["paths"]
    assert "/admin/register" in openapi["paths"]
    assert "/login" in openapi["paths"]
    print("-> Documentation paths present in OpenAPI schema!")

    print("\n==================================================")
    print(" ALL 11 TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
