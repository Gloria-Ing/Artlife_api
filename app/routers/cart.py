"""
Cart router - unified cart endpoints that work for both guests and logged-in users.

No login required to add, view, or manage the cart.

Auth detection:
  - Authenticated user (valid Bearer token)  -> account cart (carts / cart_items tables)
  - Guest (no token / invalid token)         -> session cart (guest_carts / guest_cart_items)
                                               identified by the artlife_session_id cookie,
                                               which is auto-created on the first request.

Routes:
  GET    /cart                  - View cart
  POST   /cart/items            - Add item (or increment qty if already present)
  PUT    /cart/items/{item_id}  - Update quantity of a specific item
  DELETE /cart/items/{item_id}  - Remove a single item
  DELETE /cart                  - Clear the entire cart
  POST   /cart/merge            - Merge guest cart into account cart after login (auth required)
"""

import uuid
from decimal import Decimal
from typing import Optional, Union

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Cart, CartItem, GalleryProduct, GuestCart, GuestCartItem
from app.schemas import (
    CartItemAdd,
    CartItemResponse,
    CartItemUpdate,
    CartMergeResponse,
    CartResponse,
    GuestCartItemResponse,
    GuestCartResponse,
    MessageResponse,
)
from app.security import decode_access_token, get_current_user

router = APIRouter(prefix="/cart", tags=["Cart"])

SESSION_COOKIE = "artlife_session_id"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

# Optional bearer - never raises 401 on its own
_optional_bearer = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


# ---------------------------------------------------------
# Auth helper - returns the account if token is valid,
# None if there is no token or token is invalid/expired.
# ---------------------------------------------------------

def _get_optional_user(
    token: Optional[str] = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[Account]:
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    account_id = payload.get("sub")
    if not account_id:
        return None
    return db.query(Account).filter(Account.id == int(account_id)).first()


# ---------------------------------------------------------
# Session cookie helper
# ---------------------------------------------------------

def _get_or_create_session(response: Response, session_id: Optional[str]) -> str:
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


# ---------------------------------------------------------
# Account cart helpers
# ---------------------------------------------------------

def _get_or_create_cart(account_id: int, db: Session) -> Cart:
    cart = db.query(Cart).filter(Cart.account_id == account_id).first()
    if not cart:
        cart = Cart(account_id=account_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _build_cart_response(cart: Cart, db: Session) -> CartResponse:
    items = db.query(CartItem).filter(CartItem.cart_id == cart.id).all()
    item_responses: list[CartItemResponse] = []
    total_price = Decimal("0.00")

    for item in items:
        product: Optional[GalleryProduct] = db.query(GalleryProduct).filter(
            GalleryProduct.id == item.gallery_product_id
        ).first()

        unit_price = product.price if (product and product.price) else Decimal("0.00")
        total_price += unit_price * item.quantity

        item_responses.append(CartItemResponse(
            id=item.id,
            cart_id=item.cart_id,
            gallery_product_id=item.gallery_product_id,
            quantity=item.quantity,
            added_at=item.added_at,
            product_title=product.title if product else None,
            product_price=product.price if product else None,
            product_image_url=product.image_url if product else None,
            product_status=product.status if product else None,
        ))

    return CartResponse(
        id=cart.id,
        account_id=cart.account_id,
        items=item_responses,
        total_items=sum(i.quantity for i in items),
        total_price=total_price,
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


# ---------------------------------------------------------
# Guest cart helpers
# ---------------------------------------------------------

def _get_or_create_guest_cart(session_id: str, db: Session) -> GuestCart:
    cart = db.query(GuestCart).filter(GuestCart.session_id == session_id).first()
    if not cart:
        cart = GuestCart(session_id=session_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _build_guest_cart_response(cart: GuestCart, db: Session) -> GuestCartResponse:
    items = db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == cart.id).all()
    item_responses: list[GuestCartItemResponse] = []
    total_price = Decimal("0.00")

    for item in items:
        product: Optional[GalleryProduct] = db.query(GalleryProduct).filter(
            GalleryProduct.id == item.gallery_product_id
        ).first()

        unit_price = product.price if (product and product.price) else Decimal("0.00")
        total_price += unit_price * item.quantity

        item_responses.append(GuestCartItemResponse(
            id=item.id,
            guest_cart_id=item.guest_cart_id,
            gallery_product_id=item.gallery_product_id,
            quantity=item.quantity,
            added_at=item.added_at,
            product_title=product.title if product else None,
            product_price=product.price if product else None,
            product_image_url=product.image_url if product else None,
            product_status=product.status if product else None,
        ))

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
# Shared product validation
# ---------------------------------------------------------

def _validate_product(product_id: int, db: Session) -> GalleryProduct:
    product = db.query(GalleryProduct).filter(GalleryProduct.id == product_id).first()
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
    return product


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@router.get(
    "",
    response_model=Union[CartResponse, GuestCartResponse],
    summary="View cart",
    description=(
        "Return the current cart with all items, product details, and total price. "
        "Works without login - authenticated users see their account cart, "
        "guests see their session cart (cookie auto-created on first use)."
    ),
)
def get_cart(
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(_get_optional_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Union[CartResponse, GuestCartResponse]:
    if current_user:
        return _build_cart_response(_get_or_create_cart(current_user.id, db), db)

    sid = _get_or_create_session(response, session_id)
    return _build_guest_cart_response(_get_or_create_guest_cart(sid, db), db)


@router.post(
    "/items",
    response_model=Union[CartResponse, GuestCartResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add item to cart",
    description=(
        "Add a gallery product to the cart. No login required. "
        "If the product is already in the cart the quantity is incremented. "
        "Authenticated users update their account cart; guests use a session cookie cart."
    ),
    responses={
        400: {"description": "Product is not available for purchase."},
        404: {"description": "Gallery product not found."},
    },
)
def add_to_cart(
    payload: CartItemAdd,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(_get_optional_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Union[CartResponse, GuestCartResponse]:
    _validate_product(payload.gallery_product_id, db)

    if current_user:
        cart = _get_or_create_cart(current_user.id, db)
        existing = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.gallery_product_id == payload.gallery_product_id,
        ).first()
        if existing:
            existing.quantity += payload.quantity
        else:
            db.add(CartItem(
                cart_id=cart.id,
                gallery_product_id=payload.gallery_product_id,
                quantity=payload.quantity,
            ))
        db.commit()
        db.refresh(cart)
        return _build_cart_response(cart, db)

    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)
    existing = db.query(GuestCartItem).filter(
        GuestCartItem.guest_cart_id == cart.id,
        GuestCartItem.gallery_product_id == payload.gallery_product_id,
    ).first()
    if existing:
        existing.quantity += payload.quantity
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
    response_model=Union[CartResponse, GuestCartResponse],
    summary="Update cart item quantity",
    description=(
        "Set a new quantity for an existing cart item. No login required. "
        "Operates on the account cart for authenticated users, "
        "session cart for guests."
    ),
    responses={
        404: {"description": "Cart item not found."},
    },
)
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(_get_optional_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Union[CartResponse, GuestCartResponse]:
    if current_user:
        cart = _get_or_create_cart(current_user.id, db)
        item = db.query(CartItem).filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        ).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
        item.quantity = payload.quantity
        db.commit()
        db.refresh(cart)
        return _build_cart_response(cart, db)

    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)
    item = db.query(GuestCartItem).filter(
        GuestCartItem.id == item_id,
        GuestCartItem.guest_cart_id == cart.id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    item.quantity = payload.quantity
    db.commit()
    db.refresh(cart)
    return _build_guest_cart_response(cart, db)


@router.delete(
    "/items/{item_id}",
    response_model=Union[CartResponse, GuestCartResponse],
    summary="Remove item from cart",
    description=(
        "Remove a single line item from the cart. No login required."
    ),
    responses={
        404: {"description": "Cart item not found."},
    },
)
def remove_cart_item(
    item_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(_get_optional_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> Union[CartResponse, GuestCartResponse]:
    if current_user:
        cart = _get_or_create_cart(current_user.id, db)
        item = db.query(CartItem).filter(
            CartItem.id == item_id,
            CartItem.cart_id == cart.id,
        ).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
        db.delete(item)
        db.commit()
        db.refresh(cart)
        return _build_cart_response(cart, db)

    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)
    item = db.query(GuestCartItem).filter(
        GuestCartItem.id == item_id,
        GuestCartItem.guest_cart_id == cart.id,
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    db.delete(item)
    db.commit()
    db.refresh(cart)
    return _build_guest_cart_response(cart, db)


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear cart",
    description="Remove all items from the cart. No login required.",
)
def clear_cart(
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[Account] = Depends(_get_optional_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> MessageResponse:
    if current_user:
        cart = _get_or_create_cart(current_user.id, db)
        db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        db.commit()
        return {"message": "Cart cleared successfully."}

    sid = _get_or_create_session(response, session_id)
    cart = _get_or_create_guest_cart(sid, db)
    db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == cart.id).delete()
    db.commit()
    return {"message": "Cart cleared successfully."}


@router.post(
    "/merge",
    response_model=CartMergeResponse,
    summary="Merge guest cart into account cart",
    description=(
        "After a guest logs in or registers, call this endpoint to fold all items "
        "from their guest session cart into their account cart. "
        "Quantities are summed for items that already exist in the account cart. "
        "The guest cart is cleared and the session cookie is removed on success. "
        "Requires a valid Bearer token."
    ),
    responses={
        401: {"description": "Unauthorized - valid Bearer token required."},
    },
)
def merge_guest_cart(
    response: Response,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE),
) -> CartMergeResponse:
    cart = _get_or_create_cart(current_user.id, db)

    if not session_id:
        return CartMergeResponse(
            message="No guest session found - nothing to merge.",
            items_merged=0,
            cart=_build_cart_response(cart, db),
        )

    guest_cart = db.query(GuestCart).filter(GuestCart.session_id == session_id).first()
    if not guest_cart:
        return CartMergeResponse(
            message="No guest cart found - nothing to merge.",
            items_merged=0,
            cart=_build_cart_response(cart, db),
        )

    guest_items = db.query(GuestCartItem).filter(
        GuestCartItem.guest_cart_id == guest_cart.id
    ).all()

    merged_count = 0
    for guest_item in guest_items:
        product = db.query(GalleryProduct).filter(
            GalleryProduct.id == guest_item.gallery_product_id
        ).first()
        if not product or product.status != "Available":
            continue

        existing = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.gallery_product_id == guest_item.gallery_product_id,
        ).first()
        if existing:
            existing.quantity += guest_item.quantity
        else:
            db.add(CartItem(
                cart_id=cart.id,
                gallery_product_id=guest_item.gallery_product_id,
                quantity=guest_item.quantity,
            ))
        merged_count += 1

    db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == guest_cart.id).delete()
    db.commit()
    db.refresh(cart)
    response.delete_cookie(key=SESSION_COOKIE)

    return CartMergeResponse(
        message=f"Successfully merged {merged_count} item(s) into your cart.",
        items_merged=merged_count,
        cart=_build_cart_response(cart, db),
    )
