data "aws_caller_identity" "me" {} # Define which account is used

resource "aws_s3_bucket" "raw" {
  bucket = "power-lakehouse-raw-${data.aws_caller_identity.me.account_id}"
} # Create S3 bucket; Insert account to have unique name

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
} # Block all public access

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
} # Versioning when the file is overwritten

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
} # Delete old file versions after 30 days

output "raw_bucket_name" {
  value = aws_s3_bucket.raw.bucket
}