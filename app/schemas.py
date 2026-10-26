from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Literal
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


class ProductCreate(BaseModel):
    """
    Schema for adding a product to the gallery.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Artwork or product title",
        examples=["Sunset Over Table Mountain"],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Product description shown to customers",
        examples=["Original acrylic painting inspired by Cape Town sunsets."],
    )
    price: Decimal = Field(
        ...,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Selling price for the product",
        examples=["1250.00"],
    )
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Public image URL for the product",
        examples=["https://example.com/art/sunset.jpg"],
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Product category",
        examples=["Painting"],
    )
    medium: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Artwork medium",
        examples=["Acrylic on canvas"],
    )
    dimensions: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Artwork dimensions",
        examples=["60cm x 90cm"],
    )
    stock_quantity: int = Field(
        default=1,
        ge=0,
        description="Available quantity",
        examples=[1],
    )
    is_available: bool = Field(
        default=True,
        description="Whether the product is available for sale",
        examples=[True],
    )

    @model_validator(mode="before")
    @classmethod
    def trim_product_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ["title", "description", "image_url", "category", "medium", "dimensions"]:
                if key in data and isinstance(data[key], str):
                    data[key] = data[key].strip()
        return data


class ProductResponse(ProductCreate):
    """
    Schema for product data returned to clients.
    """
    id: int = Field(..., description="Unique product identifier", examples=[1])
    created_by_id: int = Field(..., description="Admin account that created the product", examples=[1])
    created_at: Optional[datetime] = Field(default=None, description="Product creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


GalleryCategory = Literal["children", "abstract", "figurative", "heritage"]
GalleryStatus = Literal["Available", "Private Collection", "Exhibition Feature"]


class GalleryProductCreate(BaseModel):
    """
    Schema for adding an artwork to the gallery.
    """
    title: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Artwork title",
        examples=["Embers in Motion"],
    )
    series: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Artwork series or collection",
        examples=["Rhythm Studies"],
    )
    price: Decimal = Field(
        ...,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Selling price for the gallery product",
        examples=["1250.00"],
    )
    image_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Public image URL for the gallery product",
        examples=["https://example.com/art/embers-in-motion.jpg"],
    )
    category: GalleryCategory = Field(
        ...,
        description="Gallery category used by the frontend filters",
        examples=["abstract"],
    )
    year: str = Field(
        ...,
        min_length=4,
        max_length=20,
        description="Artwork year or production period",
        examples=["2026"],
    )
    medium: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Materials or technique used",
        examples=["Acrylic, charcoal, and gold leaf"],
    )
    dimensions: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Artwork dimensions",
        examples=["90 x 120 cm"],
    )
    status: GalleryStatus = Field(
        ...,
        description="Artwork availability status",
        examples=["Available"],
    )
    story: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Short narrative shown on the gallery product card",
        examples=["A layered study of movement, memory, and warm evening light."],
    )
    colors: list[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="Dominant color swatches for the gallery card",
        examples=[["#7c3aed", "#f97316", "#111827"]],
    )

    @model_validator(mode="before")
    @classmethod
    def trim_gallery_product_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ["title", "series", "image_url", "category", "year", "medium", "dimensions", "status", "story"]:
                if key in data and isinstance(data[key], str):
                    data[key] = data[key].strip()

            if "colors" in data and isinstance(data["colors"], list):
                data["colors"] = [
                    color.strip()
                    for color in data["colors"]
                    if isinstance(color, str) and color.strip()
                ]
        return data


class GalleryProductResponse(BaseModel):
    """
    Schema for gallery artwork data returned to clients.
    """
    id: int = Field(..., description="Unique gallery product identifier", examples=[1])
    title: str = Field(..., examples=["Embers in Motion"])
    series: str = Field(..., examples=["Rhythm Studies"])
    price: Optional[Decimal] = Field(default=None, examples=["1250.00"])
    image_url: Optional[str] = Field(default=None, examples=["https://example.com/art/embers-in-motion.jpg"])
    category: GalleryCategory = Field(..., examples=["abstract"])
    year: str = Field(..., examples=["2026"])
    dimensions: str = Field(..., examples=["90 x 120 cm"])
    status: GalleryStatus = Field(..., examples=["Available"])
    story: str = Field(..., examples=["A layered study of movement, memory, and warm evening light."])
    created_by_id: int = Field(..., description="Admin account that created the gallery product", examples=[1])
    created_at: Optional[datetime] = Field(default=None, description="Gallery product creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """
    Generic message response.
    """
    message: str = Field(..., examples=["Operation completed successfully"])


# -----------------------------------------
# Cart Schemas
# -----------------------------------------

class CartItemAdd(BaseModel):
    """
    Payload for adding or updating an item in the cart.
    """
    gallery_product_id: int = Field(
        ...,
        description="ID of the gallery product to add",
        examples=[3],
    )
    quantity: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Number of units to add (1-100)",
        examples=[1],
    )


class CartItemUpdate(BaseModel):
    """
    Payload for updating the quantity of an existing cart item.
    """
    quantity: int = Field(
        ...,
        ge=1,
        le=100,
        description="New quantity for the cart item (1-100)",
        examples=[2],
    )


class CartItemResponse(BaseModel):
    """
    Single cart line item returned to the client.
    """
    id: int
    cart_id: int
    gallery_product_id: int
    quantity: int
    added_at: Optional[datetime]

    # Denormalised product fields for convenience
    product_title: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_image_url: Optional[str] = None
    product_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CartResponse(BaseModel):
    """
    Full cart returned to the client, including all line items and computed total.
    """
    id: int
    account_id: int
    items: list[CartItemResponse]
    total_items: int
    total_price: Decimal
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------
# Guest Cart Schemas
# -----------------------------------------

class GuestCartItemResponse(BaseModel):
    """
    Single guest cart line item returned to the client.
    """
    id: int
    guest_cart_id: int
    gallery_product_id: int
    quantity: int
    added_at: Optional[datetime]

    # Denormalised product fields for convenience
    product_title: Optional[str] = None
    product_price: Optional[Decimal] = None
    product_image_url: Optional[str] = None
    product_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class GuestCartResponse(BaseModel):
    """
    Full guest cart returned to the client, including all line items and computed total.
    """
    id: int
    session_id: str
    items: list[GuestCartItemResponse]
    total_items: int
    total_price: Decimal
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CartMergeResponse(BaseModel):
    """
    Response returned after merging a guest cart into an authenticated user's cart.
    """
    message: str
    items_merged: int
    cart: "CartResponse"
