from tests.test_products import create_category, create_product


async def test_upload_image_happy_path(client, admin_token, fake_minio_client):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["image"].endswith(".jpg")
    assert len(fake_minio_client.uploads) == 1

    listed = await client.get(f"/products/{product_id}/images")
    assert listed.status_code == 200
    assert [img["id"] for img in listed.json()] == [body["id"]]


async def test_upload_image_requires_admin(client, admin_token, customer_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_upload_image_product_not_found(client, admin_token):
    resp = await client.post(
        "/products/00000000-0000-0000-0000-000000000000/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_upload_rejects_disallowed_content_type(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_upload_rejects_oversized_image(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    oversized = b"x" * (20 * 1024 * 1024 + 1)

    resp = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("big.jpg", oversized, "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_delete_image(client, admin_token, fake_minio_client):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    uploaded = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    image_id = uploaded.json()["id"]

    resp = await client.delete(
        f"/products/{product_id}/images/{image_id}",
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 204
    assert len(fake_minio_client.deleted_keys) == 1

    listed = await client.get(f"/products/{product_id}/images")
    assert listed.json() == []


async def test_delete_image_requires_admin(client, admin_token, customer_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    uploaded = await client.post(
        f"/products/{product_id}/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    image_id = uploaded.json()["id"]

    resp = await client.delete(
        f"/products/{product_id}/images/{image_id}",
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_delete_image_not_found(client, admin_token):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)

    resp = await client.delete(
        f"/products/{product_id}/images/00000000-0000-0000-0000-000000000000",
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 404


async def test_deleting_product_removes_its_images_from_minio(client, admin_token, fake_minio_client):
    category_id = await create_category(client, admin_token)
    product_id = await create_product(client, admin_token, category_id)
    await client.post(
        f"/products/{product_id}/images",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers={"x-internal-token": admin_token},
    )
    await client.patch(
        f"/products/{product_id}",
        json={"is_published": False},
        headers={"x-internal-token": admin_token},
    )

    resp = await client.delete(f"/products/{product_id}", headers={"x-internal-token": admin_token})
    assert resp.status_code == 204
    assert len(fake_minio_client.deleted_keys) == 1
