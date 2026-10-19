from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


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
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username used for login",
        examples=["johndoe"],
    )
    phone: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="User's phone number used for login or contact",
        examples=["+1234567890"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address",
        examples=["john.doe@example.com"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Account password (will be securely hashed)",
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
            for key in ["firstname", "lastname", "username", "phone", "email"]:
                if key in data and isinstance(data[key], str):
                    data[key] = data[key].strip()

        return data


class AccountResponse(BaseModel):
    """
    Schema for account data returned to clients (passwords are excluded).
    """
    id: int = Field(..., description="Unique account identifier", examples=[1])
    firstname: str = Field(..., examples=["John"])
    lastname: str = Field(..., examples=["Doe"])
    username: str = Field(..., examples=["johndoe"])
    phone: str = Field(..., examples=["+1234567890"])
    email: EmailStr = Field(..., examples=["john.doe@example.com"])
    role: str = Field(default="user", examples=["user"])
    created_at: Optional[datetime] = Field(default=None, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """
    Schema for logging in with username OR phone number along with password.
    """
    username_or_phone: Optional[str] = Field(
        default=None,
        description="Username or phone number to log in with",
        examples=["johndoe"],
    )
    username: Optional[str] = Field(
        default=None,
        description="Alternative field for username",
        examples=["johndoe"],
    )
    phone: Optional[str] = Field(
        default=None,
        description="Alternative field for phone number",
        examples=["+1234567890"],
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
        return data

    def get_identifier(self) -> str:
        """
        Returns the login identifier from username_or_phone, username, or phone.
        """
        val = self.username_or_phone or self.username or self.phone
        if not val or not str(val).strip():
            raise ValueError("You must provide either username_or_phone, username, or phone.")
        return str(val).strip()


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
