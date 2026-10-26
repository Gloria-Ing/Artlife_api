"""
Cart router - endpoints for managing a user's shopping cart.

All endpoints require a valid Bearer JWT token (authenticated user).

Routes:
  GET    /cart                            - View current user's cart
  POST   /cart/items                      - Add item to cart (or increment qty if already present)
  PUT    /cart/items/{item_id}            - Update quantity of a specific cart item
  DELETE /cart/items/{item_id}            - Remove a single item from the cart
  DELETE /cart                            - Clear the entire cart
  POST   /cart/merge                      - Merge guest cart into user's cart after login
"""

from decimal import Decimal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Cart, CartItem, GalleryProduct, GuestCart, GuestCartItem
from app.schemas import (
    CartItemAdd,
    CartItemResponse,
    CartItemUpdate,
    CartMergeResponse,
    CartResponse,
    MessageResponse,
)
from app.security import get_current_user

router = APIRouter(prefix="/cart", tags=["Cart"])

SESSION_COOKIE = "artlife_session_id"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _get_or_create_cart(account_id: int, db: Session) -> Cart:
    """Return the user's cart, creating one if it does not yet exist."""
    cart = db.query(Cart).filter(Cart.account_id == account_id).first()
    if not cart:
        cart = Cart(account_id=account_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _build_cart_response(cart: Cart, db: Session) -> CartResponse:
    """Assemble a CartResponse with denormalised product data and totals."""
    items = db.query(CartItem).filter(CartItem.cart_id == cart.id).all()
    item_responses: list[CartItemResponse] = []
    total_price = Decimal("0.00")

    for item in items:
        product: GalleryProduct | None = db.query(GalleryProduct).filter(
            GalleryProduct.id == item.gallery_product_id
        ).first()

        unit_price = product.price if (product and product.price) else Decimal("0.00")
        total_price += unit_price * item.quantity

        item_responses.append(
            CartItemResponse(
                id=item.id,
                cart_id=item.cart_id,
                gallery_product_id=item.gallery_product_id,
                quantity=item.quantity,
                added_at=item.added_at,
                product_title=product.title if product else None,
                product_price=product.price if product else None,
                product_image_url=product.image_url if product else None,
                product_status=product.status if product else None,
            )
        )

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
# Endpoints
# ---------------------------------------------------------

@router.get(
    "",
    response_model=CartResponse,
    summary="View cart",
    description="Return the current user's cart with all items, product details, and total price.",
)
def get_cart(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CartResponse:
    cart = _get_or_create_cart(current_user.id, db)
    return _build_cart_response(cart, db)


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to cart",
    description=(
        "Add a gallery product to the cart. If the product is already in the cart, "
        "the quantity is incremented by the requested amount."
    ),
    responses={
        404: {"description": "Gallery product not found or not available."},
    },
)
def add_to_cart(
    payload: CartItemAdd,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CartResponse:
    # Validate product exists and is available
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

    cart = _get_or_create_cart(current_user.id, db)

    # Increment if already in cart, otherwise create a new line item
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.gallery_product_id == payload.gallery_product_id,
    ).first()

    if existing_item:
        existing_item.quantity += payload.quantity
    else:
        new_item = CartItem(
            cart_id=cart.id,
            gallery_product_id=payload.gallery_product_id,
            quantity=payload.quantity,
        )
        db.add(new_item)

    db.commit()
    db.refresh(cart)
    return _build_cart_response(cart, db)


@router.put(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Update cart item quantity",
    description="Set a new quantity for an existing cart item.",
    responses={
        404: {"description": "Cart item not found in the user's cart."},
    },
)
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CartResponse:
    cart = _get_or_create_cart(current_user.id, db)

    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    item.quantity = payload.quantity
    db.commit()
    db.refresh(cart)
    return _build_cart_response(cart, db)


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove item from cart",
    description="Remove a single line item from the cart.",
    responses={
        404: {"description": "Cart item not found in the user's cart."},
    },
)
def remove_cart_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> CartResponse:
    cart = _get_or_create_cart(current_user.id, db)

    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found.",
        )

    db.delete(item)
    db.commit()
    db.refresh(cart)
    return _build_cart_response(cart, db)


@router.delete(
    "",
    response_model=MessageResponse,
    summary="Clear cart",
    description="Remove all items from the current user's cart.",
)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> MessageResponse:
    cart = _get_or_create_cart(current_user.id, db)

    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    db.commit()
    return {"message": "Cart cleared successfully."}


@router.post(
    "/merge",
    response_model=CartMergeResponse,
    summary="Merge guest cart into user cart",
    description=(
        "After a guest logs in or registers, call this endpoint to fold all items "
        "from their guest session cart into their authenticated account cart. "
        "If a product already exists in the account cart the quantities are summed. "
        "The guest cart is cleared after a successful merge. "
        "Requires a valid Bearer token and the artlife_session_id cookie."
    ),
)
def merge_guest_cart(
    response: Response,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> CartMergeResponse:
    if not session_id:
        # No guest session - nothing to merge, just return the current cart
        cart = _get_or_create_cart(current_user.id, db)
        return CartMergeResponse(
            message="No guest cart found to merge.",
            items_merged=0,
            cart=_build_cart_response(cart, db),
        )

    guest_cart = db.query(GuestCart).filter(GuestCart.session_id == session_id).first()
    if not guest_cart:
        cart = _get_or_create_cart(current_user.id, db)
        return CartMergeResponse(
            message="No guest cart found to merge.",
            items_merged=0,
            cart=_build_cart_response(cart, db),
        )

    guest_items = db.query(GuestCartItem).filter(
        GuestCartItem.guest_cart_id == guest_cart.id
    ).all()

    if not guest_items:
        cart = _get_or_create_cart(current_user.id, db)
        return CartMergeResponse(
            message="Guest cart was empty, nothing to merge.",
            items_merged=0,
            cart=_build_cart_response(cart, db),
        )

    cart = _get_or_create_cart(current_user.id, db)
    merged_count = 0

    for guest_item in guest_items:
        # Skip products that no longer exist or are unavailable
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

    # Clear the guest cart after merging
    db.query(GuestCartItem).filter(GuestCartItem.guest_cart_id == guest_cart.id).delete()
    db.commit()
    db.refresh(cart)

    # Expire the session cookie so the browser drops it
    response.delete_cookie(key=SESSION_COOKIE)

    return CartMergeResponse(
        message=f"Successfully merged {merged_count} item(s) from guest cart.",
        items_merged=merged_count,
        cart=_build_cart_response(cart, db),
    )
