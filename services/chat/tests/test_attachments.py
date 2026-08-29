import uuid

from chat.models import Room

ROOM_ID = "room_11111111-1111-1111-1111-111111111111"


async def _seed_room(app) -> None:
    async with app.state.session_factory() as session:
        session.add(Room(id=ROOM_ID, customer_id=uuid.UUID("11111111-1111-1111-1111-111111111111")))
        await session.commit()


async def test_upload_happy_path(app, client, fake_object_storage_client, customer_token):
    await _seed_room(app)
    response = await client.post(
        f"/rooms/{ROOM_ID}/attachments",
        files={"file": ("photo.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        headers=customer_token,
    )
    assert response.status_code == 200
    body = response.json()
    assert ".jpg" in body["attachment_key"]
    assert ".jpg" in body["attachment_url"]
    assert len(fake_object_storage_client.uploads) == 1


async def test_admin_can_upload_to_any_room(app, client, fake_object_storage_client, admin_token):
    await _seed_room(app)
    response = await client.post(
        f"/rooms/{ROOM_ID}/attachments",
        files={"file": ("photo.png", b"fake-png-bytes", "image/png")},
        headers=admin_token,
    )
    assert response.status_code == 200


async def test_other_customer_cannot_upload_to_someone_elses_room(app, client):
    await _seed_room(app)
    from tests.conftest import mint_internal_token

    intruder_token = mint_internal_token(sub="99999999-9999-9999-9999-999999999999", role="customer")
    response = await client.post(
        f"/rooms/{ROOM_ID}/attachments",
        files={"file": ("photo.jpg", b"bytes", "image/jpeg")},
        headers=intruder_token,
    )
    assert response.status_code == 403


async def test_rejects_disallowed_content_type(app, client, customer_token):
    await _seed_room(app)
    response = await client.post(
        f"/rooms/{ROOM_ID}/attachments",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        headers=customer_token,
    )
    assert response.status_code == 422


async def test_rejects_oversized_upload(app, client, customer_token):
    await _seed_room(app)
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    response = await client.post(
        f"/rooms/{ROOM_ID}/attachments",
        files={"file": ("big.jpg", oversized, "image/jpeg")},
        headers=customer_token,
    )
    assert response.status_code == 422
