import io
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Account, GalleryProduct
from app.schemas import GalleryCategory, GalleryProductResponse, GalleryStatus, MessageResponse
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


def optimize_image_bytes(image: UploadFile) -> tuple[bytes, str]:
    """
    Read uploaded image and optimize it to high quality yet lightweight format (<250KB).
    Returns (optimized_bytes, content_type).
    """
    raw_bytes = image.file.read()
    content_type = image.content_type or "image/jpeg"

    # Preserve animated gifs as-is
    if content_type == "image/gif":
        return raw_bytes, content_type

    try:
        pil_image = Image.open(io.BytesIO(raw_bytes))

        # Check if the image contains transparency
        has_transparency = (
            pil_image.mode in ("RGBA", "LA")
            or (pil_image.mode == "P" and "transparency" in pil_image.info)
        )

        if has_transparency:
            out_format = "PNG"
            out_content_type = "image/png"
        else:
            pil_image = pil_image.convert("RGB")
            out_format = "JPEG"
            out_content_type = "image/jpeg"

        # Downscale oversized photos to max 1600x1600 maintaining aspect ratio
        pil_image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

        out_buf = io.BytesIO()
        if out_format == "JPEG":
            pil_image.save(out_buf, format="JPEG", quality=85, optimize=True)
        else:
            pil_image.save(out_buf, format="PNG", optimize=True)

        return out_buf.getvalue(), out_content_type
    except Exception:
        # Fallback to raw bytes if PIL processing fails
        return raw_bytes, content_type


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


@router.get(
    "/gallery/products/{product_id}/image",
    summary="Get artwork image binary",
    description="Stream the persistent artwork image directly from PostgreSQL or disk cache.",
    responses={
        200: {
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/webp": {},
                "image/gif": {},
            },
            "description": "Artwork image binary.",
        },
        404: {"description": "Product or image not found."},
    },
)
def get_gallery_product_image(product_id: int, db: Session = Depends(get_db)):
    """
    Public image endpoint that serves artwork images directly from PostgreSQL.
    Survives container sleep/restarts on cloud platforms like Render.
    """
    product = db.query(GalleryProduct).filter(GalleryProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery product not found.",
        )

    # 1. Primary: serve persistent bytes from PostgreSQL
    if product.image_data:
        return Response(
            content=product.image_data,
            media_type=product.image_content_type or "image/jpeg",
            headers={
                "Cache-Control": "public, max-age=604800, immutable",
            },
        )

    # 2. Secondary fallback: check local uploads directory
    if product.image_url and product.image_url.startswith("/uploads/"):
        file_path = UPLOAD_DIR / Path(product.image_url).name
        if file_path.is_file():
            return FileResponse(
                path=file_path,
                media_type=product.image_content_type or "image/jpeg",
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                },
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found for this product.",
    )


@router.get(
    "/uploads/gallery/{filename}",
    include_in_schema=False,
)
def get_legacy_gallery_image(filename: str, db: Session = Depends(get_db)):
    """
    Fallback endpoint for existing records pointing to /uploads/gallery/{filename}.
    Checks disk first, then falls back to database image_data if present.
    """
    file_path = UPLOAD_DIR / filename
    if file_path.is_file():
        return FileResponse(path=file_path)

    target_url = f"/uploads/gallery/{filename}"
    product = db.query(GalleryProduct).filter(GalleryProduct.image_url == target_url).first()
    if product and product.image_data:
        return Response(
            content=product.image_data,
            media_type=product.image_content_type or "image/jpeg",
            headers={"Cache-Control": "public, max-age=604800, immutable"},
        )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Image not found.",
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
    Stores image binary in PostgreSQL to persist across Render sleep/restarts.
    """
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Image must be a JPG, PNG, WEBP, or GIF file.",
        )

    extension = ALLOWED_IMAGE_TYPES[image.content_type]
    filename = f"{uuid4().hex}{extension}"
    image_bytes, image_content_type = optimize_image_bytes(image)

    # Cache locally to disk
    try:
        image_path = UPLOAD_DIR / filename
        with image_path.open("wb") as destination:
            destination.write(image_bytes)
    except Exception:
        pass

    product = GalleryProduct(
        title=title.strip(),
        series=series.strip(),
        price=price,
        image_url="",
        image_data=image_bytes,
        image_content_type=image_content_type,
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

    # Set persistent database-backed URL
    product.image_url = f"/gallery/products/{product.id}/image"
    db.commit()
    db.refresh(product)
    return product


@router.put(
    "/gallery/products/{product_id}",
    response_model=GalleryProductResponse,
    summary="Update a gallery product",
    description="Update an existing gallery product. This endpoint requires an authenticated admin account.",
    responses={
        401: {"description": "Unauthorized: Missing or invalid Bearer token."},
        403: {"description": "Forbidden: Admin privileges are required."},
        404: {"description": "Gallery product not found."},
        422: {"description": "Validation error in request payload."},
    },
)
def update_gallery_product(
    product_id: int,
    title: str = Form(...),
    series: str = Form(...),
    price: Decimal = Form(...),
    category: GalleryCategory = Form(...),
    year: str = Form(...),
    dimensions: str = Form(...),
    product_status: GalleryStatus = Form(..., alias="status"),
    story: str = Form(...),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_admin: Account = Depends(get_current_admin),
):
    """
    Endpoint for admins to edit an artwork already in the gallery.
    """
    product = db.query(GalleryProduct).filter(GalleryProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery product not found.",
        )

    if image is not None:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Image must be a JPG, PNG, WEBP, or GIF file.",
            )

        extension = ALLOWED_IMAGE_TYPES[image.content_type]
        filename = f"{uuid4().hex}{extension}"
        image_bytes, image_content_type = optimize_image_bytes(image)

        try:
            image_path = UPLOAD_DIR / filename
            with image_path.open("wb") as destination:
                destination.write(image_bytes)
        except Exception:
            pass

        product.image_data = image_bytes
        product.image_content_type = image_content_type
        product.image_url = f"/gallery/products/{product.id}/image"

    product.title = title.strip()
    product.series = series.strip()
    product.price = price
    product.category = category
    product.year = year.strip()
    product.dimensions = dimensions.strip()
    product.status = product_status
    product.story = story.strip()

    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/gallery/products/{product_id}",
    response_model=MessageResponse,
    summary="Delete a gallery product",
    description="Delete an existing gallery product. This endpoint requires an authenticated admin account.",
    responses={
        401: {"description": "Unauthorized: Missing or invalid Bearer token."},
        403: {"description": "Forbidden: Admin privileges are required."},
        404: {"description": "Gallery product not found."},
    },
)
def delete_gallery_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_admin: Account = Depends(get_current_admin),
):
    """
    Endpoint for admins to remove an artwork from the gallery.
    """
    product = db.query(GalleryProduct).filter(GalleryProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery product not found.",
        )

    db.delete(product)
    db.commit()
    return {"message": "Gallery product deleted successfully."}
