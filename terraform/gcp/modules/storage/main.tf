# One GCS bucket replacing base's `object-storage` StatefulSet (MinIO
# locally), holding both buckets it had (chat-attachments,
# catalog-product-images) as top-level prefixes — GCS has no native
# "multi-bucket-in-one-server" concept to mirror 1:1, and catalog/chat only
# ever construct object keys, never list buckets. The prefix separation is
# applied by ObjectStorageClient's key_prefix (see object_storage_client.py
# in both), fed from OBJECT_STORAGE_KEY_PREFIX -- set by
# k8s/overlays/gcp/generate-overlay.py's generated ConfigMap patch, empty in
# base/local dev where each service already has its own real MinIO bucket.
# Accessed via GCS's S3-compatible XML API + an HMAC key pair (not the
# native google-cloud-storage SDK) so services/catalog and services/chat's
# existing boto3 client needs no *other* code changes — only
# OBJECT_STORAGE_ENDPOINT/bucket/access keys/prefix, all config, differ
# between environments.

resource "google_storage_bucket" "assets" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # required for `terraform destroy` to remove a non-empty bucket cleanly

  # Enforced, not "inherited" -- this bucket must never become public
  # regardless of org policy or a future accidental allUsers/
  # allAuthenticatedUsers IAM grant. Same posture as local dev's MinIO,
  # whose object-storage-init Job deliberately does *not* run
  # `mc anonymous set download` (it used to): catalog/chat never expose a
  # durable public link, in either environment -- every image/attachment
  # URL is a short-lived presigned GET, generated on read (see
  # ObjectStorageClient.generate_presigned_url in both), never stored.
  public_access_prevention = "enforced"
}

resource "google_service_account" "hmac_user" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-gcs-hmac"
  display_name = "HMAC key holder for the GCS S3-compatible endpoint (catalog/chat boto3 clients)"
}

resource "google_storage_bucket_iam_member" "hmac_user_object_admin" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.hmac_user.email}"
}

resource "google_storage_hmac_key" "assets" {
  project               = var.project_id
  service_account_email = google_service_account.hmac_user.email
}
