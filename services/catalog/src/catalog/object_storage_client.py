import asyncio

import boto3


class ObjectStorageClient:
    """S3-compatible client against an object-storage bucket. boto3 is
    synchronous, so all calls run in a thread via asyncio.to_thread rather
    than blocking the event loop.

    Dev gap, documented in README.md: MinIO stands in for S3+CloudFront in
    local dev; in GCP (see terraform/gcp/modules/storage) the same class
    talks to a GCS bucket over its S3-compatible XML API instead. Either
    way the bucket is private (no public/anonymous read access -- nothing
    here relies on it) -- callers get a short-lived presigned GET URL from
    `generate_presigned_url`, computed fresh on every read, never a
    permanent public link stored anywhere.

    Two internal boto3 clients, not one: `_client` talks to `endpoint` (the
    container-network address this service actually reaches the bucket
    through) for put_object/delete_object, but presigned URLs must be
    *signed* against the host a browser will actually request them from
    (SigV4 signs the Host header itself) -- that's `public_base_url`
    (`http://localhost:9000` in dev, same GCS endpoint as `endpoint` on
    GCP), so `_presign_client` is a second client built against it, used
    only by generate_presigned_url.

    `key_prefix` namespaces every key this instance writes/deletes/signs --
    empty in local dev (catalog/chat each get their own real MinIO bucket
    there), non-empty on GCP where catalog and chat share one physical GCS
    bucket (see terraform/gcp/modules/storage's comment) and rely on this
    prefix instead of separate buckets to stay isolated. Callers (routers)
    pass bare keys either way and never see the prefix -- it's applied
    here, once, so a caller's own object_key (what it stores in its DB)
    never needs to change based on which environment it's running in."""

    def __init__(
        self,
        endpoint: str,
        public_base_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        key_prefix: str = "",
        presigned_url_ttl_seconds: int = 900,
    ) -> None:
        self._bucket = bucket
        self._key_prefix = key_prefix
        self._presigned_url_ttl_seconds = presigned_url_ttl_seconds
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=public_base_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=f"{self._key_prefix}{key}",
            Body=body,
            ContentType=content_type,
        )

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=f"{self._key_prefix}{key}")

    async def generate_presigned_url(self, key: str) -> str:
        return await asyncio.to_thread(
            self._presign_client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": f"{self._key_prefix}{key}"},
            ExpiresIn=self._presigned_url_ttl_seconds,
        )
