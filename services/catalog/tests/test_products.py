async def create_category(client, admin_token, name="Drinks") -> str:
    resp = await client.post(
        "/categories",
        json={"name": name},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_create_product_requires_admin(client, customer_token, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": category_id},
        headers={"x-internal-token": customer_token},
    )
    assert resp.status_code == 403


async def test_create_product_as_admin_succeeds(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={
            "name": "Cola",
            "price": 1.5,
            "category_id": category_id,
            "description": "Fizzy drink",
            "min_temperature": 2,
            "max_temperature": 8,
        },
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Cola"
    assert body["category_id"] == category_id


async def test_create_product_unknown_category_rejected(client, admin_token):
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": "00000000-0000-0000-0000-000000000000"},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_create_product_non_positive_price_rejected(client, admin_token):
    category_id = await create_category(client, admin_token)
    resp = await client.post(
        "/products",
        json={"name": "Cola", "price": 0, "category_id": category_id},
        headers={"x-internal-token": admin_token},
    )
    assert resp.status_code == 422


async def test_list_and_get_product(client, admin_token):
    category_id = await create_category(client, admin_token)
    created = await client.post(
        "/products",
        json={"name": "Cola", "price": 1.5, "category_id": category_id},
        headers={"x-internal-token": admin_token},
    )
    product_id = created.json()["id"]

    listed = await client.get("/products")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [product_id]

    fetched = await client.get(f"/products/{product_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Cola"


async def test_get_product_not_found(client):
    resp = await client.get("/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
