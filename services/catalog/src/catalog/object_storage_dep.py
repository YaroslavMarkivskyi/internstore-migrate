from fastapi import Request

from catalog.object_storage_client import ObjectStorageClient


def get_object_storage_client(request: Request) -> ObjectStorageClient:
    return request.app.state.object_storage_client
