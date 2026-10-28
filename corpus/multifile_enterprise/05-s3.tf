resource "aws_s3_bucket" "flow_logs" {
  bucket = "${var.project}-flow-logs"
  tags = merge(local.common_tags, { Purpose = "network-monitoring" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "flow_logs" {
  bucket = aws_s3_bucket.flow_logs.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project}-artifacts"
  tags = merge(local.common_tags, { Purpose = "ci-cd" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.project}-tfstate"
  tags = merge(local.common_tags, { Purpose = "infrastructure" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" } }
}
resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration { status = "Enabled" }
}

# ===== THE VULNERABLE BUCKET — PII exports, NO encryption =====
resource "aws_s3_bucket" "customer_exports" {
  bucket = "${var.project}-customer-data-exports"
  tags = merge(local.common_tags, { Purpose = "analytics", DataClassification = "pii" })
}
# NOTE: No encryption configuration for this bucket!

resource "aws_s3_bucket" "static_assets" {
  bucket = "${var.project}-static-assets"
  tags = merge(local.common_tags, { Purpose = "frontend" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "static_assets" {
  bucket = aws_s3_bucket.static_assets.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket" "ml_training" {
  bucket = "${var.project}-ml-training"
  tags = merge(local.common_tags, { Purpose = "machine-learning" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "ml_training" {
  bucket = aws_s3_bucket.ml_training.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" } }
}

resource "aws_s3_bucket" "backup_archive" {
  bucket = "${var.project}-backup-archive"
  tags = merge(local.common_tags, { Purpose = "disaster-recovery" })
}
resource "aws_s3_bucket_server_side_encryption_configuration" "backup_archive" {
  bucket = aws_s3_bucket.backup_archive.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}
