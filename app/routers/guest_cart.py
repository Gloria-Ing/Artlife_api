"""
Guest Cart router - endpoints for managing an anonymous user's shopping cart.

A session_id UUID is automatically issued as a cookie on the first request and
used to identify the guest cart on all subsequent calls. No account is needed.

When the guest eventually registers or logs in, they call POST /cart/merge
(on the authenticated cart router) to fold their guest items into their account cart.

Routes:
  GET    /guest/cart                      - View the guest cart
  POST   /guest/cart/items                - Add item (or increment qty if already present)
  PUT    /guest/cart/items/{item_id}      - Update quantity of a specific item
  DELETE /guest/cart/items/{item_id}      - Remove a single item
  DELETE /guest/cart                      - Clear the entire guest cart
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GalleryProduct, GuestCart, GuestCartItem
from app.schemas import (
    CartItemAdd,
    CartItemUpdate,
    GuestCartItemResponse,
    GuestCartResponse,
    MessageResponse,
)

router = APIRouter(prefix="/guest/cart", tags=["Guest Cart"])

# Cookie name used to persist the guest session
SESSION_COOKIE = "artlife_session_id"
# 30-day TTL (seconds)
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _get_or_create_session(
    response: Response,
    session_id: str | None,
) -> str:
    """
    Return the existing session_id or mint a new UUID and set it as a cookie.
    """
    if session_id:
        return session_id

    new_sid = uuid.uuid4().hex
    response.set_cookie(
        key=SESSION_COOKIE,
        value=new_sid,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return new_sid


def _get_or_create_guest_cart(session_id: str, db: Session) -> GuestCart:
    """Return the guest cart for the session, creating one if it does not yet exist."""
    cart = db.query(GuestCart).filter(GuestCart.session_id == session_id).first()
    if not cart:
        cart = GuestCart(session_id=session_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _build_guest_cart_response(cart: GuestCart, db: Session) -> GuestCartResponse:
    """Assemble a GuestCartResponse with denormalised product data and totals."""
    items = db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == cart.id).all()
    item_responses: list[GuestCartItemResponse] = []
    total_price = Decimal("0.00")

    for item in items:
        product: GalleryProduct | None = db.query(GalleryProduct).filter(
            GalleryProduct.id == item.gallery_product_id
        ).first()

        unit_price = product.price if (product and product.price) else Decimal("0.00")
        total_price += unit_price * item.quantity

        item_responses.append(
            GuestCartItemResponse(
                id=item.id,
                guest_cart_id=item.guest_cart_id,
                gallery_product_id=item.gallery_product_id,
                quantity=item.quantity,
                added_at=item.added_at,
                product_title=product.title if product else None,
                product_price=product.price if product else None,
                product_image_url=product.image_url if product else None,
                product_status=product.status if product else None,
            )
        )

    return GuestCartResponse(
        id=cart.id,
        session_id=cart.session_id,
        items=item_responses,
        total_items=sum(i.quantity for i in items),
        total_price=total_price,
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.get(
    "",
    response_model=GuestCartResponse,
    summary="View guest cart",
    description=(
        "Return the guest cart for this browser session. "
        "A session cookie is automatically created if one does not exist yet."
    ),
)
def get_guest_cart(
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> GuestCartResponse:
    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)
    return _build_guest_cart_response(cart, db)


@router.post(
    "/items",
    response_model=GuestCartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to guest cart",
    description=(
        "Add a gallery product to the guest cart. "
        "If the product is already in the cart the quantity is incremented. "
        "A session cookie is automatically created if one does not exist yet."
    ),
    responses={
        400: {"description": "Product is not available for purchase."},
        404: {"description": "Gallery product not found."},
    },
)
def add_to_guest_cart(
    payload: CartItemAdd,
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> GuestCartResponse:
    sid = _get_or_create_session(response, session_id)

    # Validate product
    product = db.query(GalleryProduct).filter(
        GalleryProduct.id == payload.gallery_product_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery product not found.",
        )

    if product.status != "Available":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{product.title}' is not available for purchase (status: {product.status}).",
        )

    cart = _get_or_create_guest_cart(sid, db)

    existing_item = db.query(GuestCartItem).filter(
        GuestCartItem.guest_cart_id == cart.id,
        GuestCartItem.gallery_product_id == payload.gallery_product_id,
    ).first()

    if existing_item:
        existing_item.quantity += payload.quantity
    else:
        db.add(GuestCartItem(
            guest_cart_id=cart.id,
            gallery_product_id=payload.gallery_product_id,
            quantity=payload.quantity,
        ))

    db.commit()
    db.refresh(cart)
    return _build_guest_cart_response(cart, db)


@router.put(
    "/items/{item_id}",
    response_model=GuestCartResponse,
    summary="Update guest cart item quantity",
    description="Set a new quantity for an existing guest cart item.",
    responses={
        404: {"description": "Cart item not found in this guest session."},
    },
)
def update_guest_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> GuestCartResponse:
    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)

    item = db.query(GuestCartItem).filter(
        GuestCartItem.id == item_id,
        GuestCartItem.guest_cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    item.quantity = payload.quantity
    db.commit()
    db.refresh(cart)
    return _build_guest_cart_response(cart, db)


@router.delete(
    "/items/{item_id}",
    response_model=GuestCartResponse,
    summary="Remove item from guest cart",
    description="Remove a single line item from the guest cart.",
    responses={
        404: {"description": "Cart item not found in this guest session."},
    },
)
def remove_guest_cart_item(
    item_id: int,
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> GuestCartResponse:
    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)

    item = db.query(GuestCartItem).filter(
        GuestCartItem.id == item_id,
        GuestCartItem.guest_cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    db.delete(item)
    db.commit()
    db.refresh(cart)
    return _build_guest_cart_response(cart, db)


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear guest cart",
    description="Remove all items from the guest cart for this session.",
)
def clear_guest_cart(
    response: Response,
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> MessageResponse:
    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)

    db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == cart.id).delete()
    db.commit()
    return {"message": "Guest cart cleared successfully."}
