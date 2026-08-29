output "bucket_name" {
  value = google_storage_bucket.assets.name
}

output "s3_compatible_endpoint" {
  description = "OBJECT_STORAGE_ENDPOINT equivalent for the boto3 client"
  value       = "https://storage.googleapis.com"
}

output "hmac_access_id" {
  value = google_storage_hmac_key.assets.access_id
}

output "hmac_secret" {
  value     = google_storage_hmac_key.assets.secret
  sensitive = true
}
