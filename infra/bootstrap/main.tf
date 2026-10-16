terraform {

  required_version = ">= 1.10.0, < 2.0.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0"
    }
  }

}
provider "aws" {
  region = var.region
}
variable "region" {
  default = "us-east-1"
}
variable "state_bucket" {
  type = string
}
variable "github_repository" {
  type = string
}
resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket
  tags   = { Project = "securetask", Repository = var.github_repository, ManagedBy = "Terraform" }
}
resource "aws_s3_bucket_versioning" "state" {

  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }

}
resource "aws_s3_bucket_server_side_encryption_configuration" "state" {

  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }

}
resource "aws_s3_bucket_public_access_block" "state" {

  bucket            = aws_s3_bucket.state.id
  block_public_acls = true
  # VIDEO CHALLENGE 1: set this to true to pass CKV2_AKUPHE_1.
  # The provisioning preflight blocks bootstrap while it is false.
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = true

}
resource "aws_s3_bucket_policy" "state" {

  bucket = aws_s3_bucket.state.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Deny", Principal = "*", Action = "s3:*", Resource = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false"
    }
    }
    }]
  })

}
output "bucket" {
  value = aws_s3_bucket.state.id
}
