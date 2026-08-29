from fastapi import Request

from chat.minio_client import MinioClient


def get_minio_client(request: Request) -> MinioClient:
    return request.app.state.minio_client
