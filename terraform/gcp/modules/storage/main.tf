# One GCS bucket replacing base's `minio` StatefulSet, holding both buckets
# MinIO had (chat-attachments, catalog-product-images) as top-level prefixes
# — GCS has no native "multi-bucket-in-one-server" concept to mirror 1:1,
# and catalog/chat only ever construct object keys, never list buckets, so
# a single bucket with two prefixes is a no-app-code-change swap. Accessed
# via GCS's S3-compatible XML API + an HMAC key pair (not the native
# google-cloud-storage SDK) specifically so services/catalog and
# services/chat's existing boto3 client (see minio_client.py in both) needs
# zero code changes — only MINIO_ENDPOINT/access keys change, per STR-154's
# "no application code changes" constraint.

resource "google_storage_bucket" "assets" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # required for `terraform destroy` to remove a non-empty bucket cleanly

  public_access_prevention = "inherited" # catalog/chat set per-object ACLs the same way MinIO's `mc anonymous set download` did
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
