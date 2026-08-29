from fastapi import Request

from chat.object_storage_client import ObjectStorageClient


def get_object_storage_client(request: Request) -> ObjectStorageClient:
    return request.app.state.object_storage_client


async def resolve_attachment_url(client: ObjectStorageClient, attachment_key: str | None) -> str | None:
    """Every outbound message representation (get_messages, _send_history,
    the live pub/sub publish) calls this at serve time, never storing the
    result -- see Message.attachment_key's docstring."""
    if attachment_key is None:
        return None
    return await client.generate_presigned_url(attachment_key)
