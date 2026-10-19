from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator


class AccountCreate(BaseModel):
    """
    Schema for account registration.
    """
    id: Optional[int] = Field(
        default=None,
        description="Optional custom account ID. If omitted or null, PostgreSQL will auto-generate it.",
        examples=[1],
    )
    firstname: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's first name",
        examples=["John"],
    )
    lastname: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's last name",
        examples=["Doe"],
    )
    phone: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="User's phone number used for contact",
        examples=["+1234567890"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address",
        examples=["john.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Strong account password (will be securely hashed)",
        examples=["SecretPassword123!"],
    )

    @model_validator(mode="before")
    @classmethod
    def handle_field_aliases_and_whitespace(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Support typo 'passord' if provided
            if "passord" in data and ("password" not in data or not data["password"]):
                data["password"] = data["passord"]

            # Trim whitespace from string fields
            for key in ["firstname", "lastname", "phone", "email"]:
                if key in data and isinstance(data[key], str):
                    data[key] = data[key].strip()

        return data

    @field_validator("password")
    @classmethod
    def validate_strong_password(cls, password: str) -> str:
        """
        Require strong passwords for all new user and admin accounts.
        """
        checks = [
            (any(char.islower() for char in password), "one lowercase letter"),
            (any(char.isupper() for char in password), "one uppercase letter"),
            (any(char.isdigit() for char in password), "one number"),
            (any(not char.isalnum() for char in password), "one special character"),
        ]
        missing = [message for passed, message in checks if not passed]
        if missing:
            raise ValueError(
                "Password must include at least "
                + ", ".join(missing)
                + "."
            )
        return password


class AccountResponse(BaseModel):
    """
    Schema for account data returned to clients (passwords are excluded).
    """
    id: int = Field(..., description="Unique account identifier", examples=[1])
    firstname: str = Field(..., examples=["John"])
    lastname: str = Field(..., examples=["Doe"])
    phone: str = Field(..., examples=["+1234567890"])
    email: EmailStr = Field(..., examples=["john.doe@example.com"])
    role: str = Field(default="user", examples=["user"])
    created_at: Optional[datetime] = Field(default=None, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """
    Schema for logging in with email and password.
    """
    email: EmailStr = Field(
        ...,
        description="Email address to log in with",
        examples=["john.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
        examples=["SecretPassword123!"],
    )

    @model_validator(mode="before")
    @classmethod
    def handle_login_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Support typo 'passord' if provided
            if "passord" in data and ("password" not in data or not data["password"]):
                data["password"] = data["passord"]

            if "email" in data and isinstance(data["email"], str):
                data["email"] = data["email"].strip()
        return data


class LoginResponse(BaseModel):
    """
    Schema for successful login response containing JWT access token and user information.
    """
    message: str = Field(default="Login successful", examples=["Login successful"])
    access_token: str = Field(..., description="JWT Bearer token", examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    token_type: str = Field(default="bearer", examples=["bearer"])
    user: AccountResponse


class AdminAccountResponse(AccountResponse):
    """
    Schema for admin account data returned to clients.
    """
    role: str = Field(default="admin", examples=["admin"])


class MessageResponse(BaseModel):
    """
    Generic message response.
    """
    message: str = Field(..., examples=["Operation completed successfully"])
