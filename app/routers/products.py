from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, GalleryProduct
from app.schemas import GalleryCategory, GalleryProductResponse, GalleryStatus
from app.security import get_current_admin

router = APIRouter(tags=["Gallery Products"])

GALLERY_CATEGORIES = ("children", "abstract", "figurative", "heritage")
GALLERY_STATUSES = ("Available", "Private Collection", "Exhibition Feature")
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "gallery"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


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
    title: str = Form(...),
    series: str = Form(...),
    price: Decimal = Form(...),
    category: GalleryCategory = Form(...),
    year: str = Form(...),
    dimensions: str = Form(...),
    product_status: GalleryStatus = Form(..., alias="status"),
    story: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: Account = Depends(get_current_admin),
):
    """
    Endpoint for admins to add an artwork to the gallery.
    """
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be a JPG, PNG, WEBP, or GIF file.",
        )

    extension = ALLOWED_IMAGE_TYPES[image.content_type]
    filename = f"{uuid4().hex}{extension}"
    image_path = UPLOAD_DIR / filename

    with image_path.open("wb") as destination:
        while chunk := image.file.read(1024 * 1024):
            destination.write(chunk)

    product = GalleryProduct(
        title=title.strip(),
        series=series.strip(),
        price=price,
        image_url=f"/uploads/gallery/{filename}",
        category=category,
        year=year.strip(),
        medium="",
        dimensions=dimensions.strip(),
        status=product_status,
        story=story.strip(),
        colors=[],
        created_by_id=current_admin.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
