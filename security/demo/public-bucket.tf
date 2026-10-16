# SCAN-ONLY FIXTURE. Never apply this configuration.
resource "aws_s3_bucket" "demo" {
  bucket = "securetask-scan-only-example"
}
resource "aws_s3_bucket_public_access_block" "demo" {
  bucket = aws_s3_bucket.demo.id
  block_public_acls = false
  block_public_policy = false
  ignore_public_acls = false
  restrict_public_buckets = false
}
