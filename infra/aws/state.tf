resource "aws_s3_bucket" "tfstate" {
  bucket = "power-lakehouse-tfstate-${data.aws_caller_identity.me.account_id}"

  lifecycle {
    prevent_destroy = true   # Terraform refuses to delete this bucket
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

output "tfstate_bucket_name" {
  value = aws_s3_bucket.tfstate.bucket
}