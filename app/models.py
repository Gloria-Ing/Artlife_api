from sqlalchemy import Column, Integer, String, DateTime
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
