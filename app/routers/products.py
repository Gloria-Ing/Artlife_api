from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, Product
from app.schemas import ProductCreate, ProductResponse
from app.security import get_current_admin

router = APIRouter(tags=["Gallery Products"])


@router.post(
    "/gallery/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product to the gallery",
    description=(
        "Create a new art product listing in the gallery. This endpoint requires an "
        "authenticated admin account."
    ),
    responses={
        201: {"description": "Product added to the gallery successfully."},
        401: {"description": "Unauthorized: Missing or invalid Bearer token."},
        403: {"description": "Forbidden: Admin privileges are required."},
        422: {"description": "Validation error in request payload."},
    },
)
def create_gallery_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_admin: Account = Depends(get_current_admin),
):
    """
    Endpoint for admins to add a product to the gallery.
    """
    product = Product(
        title=product_in.title,
        description=product_in.description,
        price=product_in.price,
        image_url=product_in.image_url,
        category=product_in.category,
        medium=product_in.medium,
        dimensions=product_in.dimensions,
        stock_quantity=product_in.stock_quantity,
        is_available=product_in.is_available,
        created_by_id=current_admin.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
