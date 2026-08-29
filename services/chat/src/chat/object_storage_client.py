import asyncio

import boto3


class MinioClient:
    """S3-compatible client against MinIO. boto3 is synchronous, so uploads
    run in a thread via asyncio.to_thread rather than blocking the event
    loop — this is the only outbound I/O in the service that isn't already
    async-native (DB, Kafka, Redis all are).

    Dev gap, documented in README.md: MinIO stands in for S3+CloudFront.
    `minio_public_base_url` (host-exposed :9000) is what a browser loads
    attachment_url from directly; in prod this would be a signed/CDN URL
    instead, and only the boto3 client construction below would need to
    change (endpoint + credentials), not any calling code."""

    def __init__(
        self,
        endpoint: str,
        public_base_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self._public_base_url = public_base_url.rstrip("/")
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def put_object(self, key: str, body: bytes, content_type: str) -> str:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return f"{self._public_base_url}/{self._bucket}/{key}"
