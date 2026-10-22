from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, LargeBinary, Numeric, String, Text
from sqlalchemy.sql import func
from app.database import Base


class Account(Base):
    """
    SQLAlchemy model representing an account in the PostgreSQL database.
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    phone = Column(String(30), unique=True, index=True, nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user", server_default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, email='{self.email}', role='{self.role}')>"


class Product(Base):
    """
    SQLAlchemy model representing an art product listed in the gallery.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    image_url = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True)
    medium = Column(String(100), nullable=True)
    dimensions = Column(String(100), nullable=True)
    stock_quantity = Column(Integer, nullable=False, default=1, server_default="1")
    is_available = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, title='{self.title}', price='{self.price}')>"


class GalleryProduct(Base):
    """
    SQLAlchemy model representing an artwork shown in the public gallery.
    """
    __tablename__ = "gallery_products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(150), nullable=False, index=True)
    series = Column(String(150), nullable=False)
    price = Column(Numeric(10, 2), nullable=True)
    image_url = Column(String(500), nullable=True)
    image_data = Column(LargeBinary, nullable=True)
    image_content_type = Column(String(100), nullable=True)
    category = Column(String(50), nullable=False)
    year = Column(String(20), nullable=False)
    medium = Column(String(120), nullable=False)
    dimensions = Column(String(120), nullable=False)
    status = Column(String(50), nullable=False, default="Available", server_default="Available")
    story = Column(Text, nullable=False)
    colors = Column(JSON, nullable=False, default=list)
    created_by_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<GalleryProduct(id={self.id}, title='{self.title}', status='{self.status}')>"


class Cart(Base):
    """
    SQLAlchemy model representing a user's shopping cart.
    One cart per user (created on first add-to-cart).
    """
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Cart(id={self.id}, account_id={self.account_id})>"


class CartItem(Base):
    """
    SQLAlchemy model representing a single line item inside a cart.
    Each row links a Cart to a GalleryProduct with a quantity.
    """
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True)
    gallery_product_id = Column(Integer, ForeignKey("gallery_products.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1, server_default="1")
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CartItem(id={self.id}, cart_id={self.cart_id}, gallery_product_id={self.gallery_product_id}, qty={self.quantity})>"
