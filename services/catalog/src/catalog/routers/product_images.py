import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.auth import require_admin
from catalog.db import get_session
from catalog.minio_client import MinioClient
from catalog.minio_dep import get_minio_client
from catalog.models import Product, ProductImage
from catalog.schemas import ProductImageRead

router = APIRouter(prefix="/products", tags=["product-images"])

# Same limits as Chat's attachment upload (services/chat/src/chat/routers/
# attachments.py) -- the frontend's MAX_FILE_SIZE/accepted types already
# assume exactly this.
ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png"}
MAX_SIZE_BYTES = 20 * 1024 * 1024


async def _get_product_or_404(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{product_id}/images", response_model=list[ProductImageRead])
async def list_product_images(
    product_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProductImage]:
    await _get_product_or_404(session, product_id)
    result = await session.execute(
        select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def add_product_image(
    product_id: uuid.UUID,
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    minio_client: Annotated[MinioClient, Depends(get_minio_client)],
) -> ProductImage:
    await _get_product_or_404(session, product_id)

    extension = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=422, detail="Only JPEG and PNG images are supported")

    body = await file.read(MAX_SIZE_BYTES + 1)
    if len(body) > MAX_SIZE_BYTES:
        raise HTTPException(status_code=422, detail="Image exceeds the 20MB limit")

    key = f"{product_id}/{uuid.uuid4()}.{extension}"
    image_url = await minio_client.put_object(key, body, file.content_type)

    image = ProductImage(product_id=product_id, image=image_url, object_key=key)
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


@router.delete("/{product_id}/images/{image_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    minio_client: Annotated[MinioClient, Depends(get_minio_client)],
) -> None:
    image = await session.get(ProductImage, image_id)
    if image is None or image.product_id != product_id:
        raise HTTPException(status_code=404, detail="Image not found")

    await minio_client.delete_object(image.object_key)
    await session.delete(image)
    await session.commit()
