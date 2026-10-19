from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, GalleryProduct
from app.schemas import GalleryProductCreate, GalleryProductResponse
from app.security import get_current_admin

router = APIRouter(tags=["Gallery Products"])

GALLERY_CATEGORIES = ("children", "abstract", "figurative", "heritage")
GALLERY_STATUSES = ("Available", "Private Collection", "Exhibition Feature")


@router.get(
    "/gallery/products",
    response_model=list[GalleryProductResponse],
    summary="List gallery products",
    description="Retrieve artworks shown in the public gallery.",
)
def list_gallery_products(db: Session = Depends(get_db)):
    """
    Public endpoint for loading gallery artworks.
    """
    return (
        db.query(GalleryProduct)
        .filter(GalleryProduct.category.in_(GALLERY_CATEGORIES))
        .filter(GalleryProduct.status.in_(GALLERY_STATUSES))
        .order_by(GalleryProduct.created_at.desc(), GalleryProduct.id.desc())
        .all()
    )


@router.post(
    "/gallery/products",
    response_model=GalleryProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product to the gallery",
    description=(
        "Create a new artwork listing in the gallery. This endpoint requires an "
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
    product_in: GalleryProductCreate,
    db: Session = Depends(get_db),
    current_admin: Account = Depends(get_current_admin),
):
    """
    Endpoint for admins to add an artwork to the gallery.
    """
    product = GalleryProduct(
        title=product_in.title,
        series=product_in.series,
        price=product_in.price,
        image_url=product_in.image_url,
        category=product_in.category,
        year=product_in.year,
        medium=product_in.medium,
        dimensions=product_in.dimensions,
        status=product_in.status,
        story=product_in.story,
        colors=product_in.colors,
        created_by_id=current_admin.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
