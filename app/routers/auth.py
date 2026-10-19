from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account
from app.schemas import (
    AccountCreate,
    AccountResponse,
    AdminAccountResponse,
    LoginRequest,
    LoginResponse,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(tags=["Authentication & Accounts"])


def _create_account(account_in: AccountCreate, db: Session, role: str = "user") -> Account:
    """
    Create an account after validating unique identifiers.
    """
    # Check if custom ID was provided and is already registered
    if account_in.id is not None:
        existing_id = db.query(Account).filter(Account.id == account_in.id).first()
        if existing_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with ID '{account_in.id}' already exists.",
            )

    # Check unique email
    existing_email = db.query(Account).filter(Account.email == account_in.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{account_in.email}' is already registered.",
        )

    # Check unique phone
    existing_phone = db.query(Account).filter(Account.phone == account_in.phone).first()
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Phone number '{account_in.phone}' is already registered.",
        )

    # Securely hash the password
    password_hash = hash_password(account_in.password)

    # Build account instance
    account_data = {
        "firstname": account_in.firstname,
        "lastname": account_in.lastname,
        "phone": account_in.phone,
        "email": account_in.email,
        "password_hash": password_hash,
        "role": role,
    }
    if account_in.id is not None:
        account_data["id"] = account_in.id

    new_account = Account(**account_data)
    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    return new_account


@router.post(
    "/register",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
    description=(
        "Create a new user account with `id`, `firstname`, `lastname`, `phone`, `email`, "
        "and a strong `password`. If `id` is omitted or null, PostgreSQL will automatically "
        "generate an auto-incrementing ID. Passwords are securely hashed with bcrypt."
    ),
    responses={
        201: {"description": "Account created successfully."},
        409: {"description": "Conflict: Email, phone, or custom ID already exists."},
        422: {"description": "Validation error in request payload."},
    },
)
def register(account_in: AccountCreate, db: Session = Depends(get_db)):
    """
    Endpoint to register a new account.
    """
    return _create_account(account_in=account_in, db=db, role="user")


@router.post(
    "/admin/register",
    response_model=AdminAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new admin account",
    description=(
        "Create an admin account with the same fields as a normal account, but store it with "
        "`role='admin'` so it is different from customer/user accounts."
    ),
    responses={
        201: {"description": "Admin account created successfully."},
        409: {"description": "Conflict: Email, phone, or custom ID already exists."},
        422: {"description": "Validation error in request payload."},
    },
)
def register_admin(account_in: AccountCreate, db: Session = Depends(get_db)):
    """
    Endpoint to register a new admin account.
    """
    return _create_account(account_in=account_in, db=db, role="admin")


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    description=(
        "Authenticate a user using their **email address** and password. Upon successful "
        "authentication, a JWT Bearer token and user account information are returned."
    ),
    responses={
        200: {"description": "Login successful with JWT access token."},
        401: {"description": "Unauthorized: Invalid email or password."},
        422: {"description": "Validation error: Missing email or password."},
    },
)
def login(login_in: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint for user login using email and password.
    """
    account = db.query(Account).filter(Account.email == login_in.email).first()

    if not account or not verify_password(login_in.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create signed JWT token
    access_token = create_access_token(
        data={
            "sub": str(account.id),
            "email": account.email,
            "role": account.role,
        }
    )

    return LoginResponse(
        message="Login successful",
        access_token=access_token,
        token_type="bearer",
        user=account,
    )


@router.get(
    "/me",
    response_model=AccountResponse,
    summary="Get current logged-in user profile",
    description="Retrieve the authenticated user's account details using the Bearer JWT token.",
)
def get_me(current_user: Account = Depends(get_current_user)):
    """
    Protected endpoint to fetch current user profile.
    """
    return current_user


@router.get(
    "/accounts",
    response_model=List[AccountResponse],
    summary="List all accounts",
    description="Retrieve a list of all registered accounts (password hashes omitted).",
)
def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Utility endpoint to view registered accounts.
    """
    return db.query(Account).offset(skip).limit(limit).all()
