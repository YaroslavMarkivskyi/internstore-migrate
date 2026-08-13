# GCS-backed remote state. The ticket's module tree shows backend.tf at
# terraform/gcp/ root, but a Terraform backend block can only live in the
# root module actually being applied — environments/demo is that root
# module, so this file lives here instead. Documented deviation, not a
# silent one (see README.md "Deviations from the ticket").
#
# The bucket itself is created once by ../../bootstrap.sh, *outside*
# Terraform (a state backend can't bootstrap the bucket it stores its own
# state in) — it is NOT part of the destroyable stack and `terraform
# destroy` never touches it.
terraform {
  backend "gcs" {
    # Set via: terraform init -backend-config="bucket=<your-tfstate-bucket>"
    prefix = "internstore-demo"
  }
}
