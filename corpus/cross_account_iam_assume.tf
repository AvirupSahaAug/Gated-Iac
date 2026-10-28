# Scenario 4: Cross-Account Role Assumption with Overly Permissive Trust Policy
# Demonstrates an IAM architectural vulnerability where sensitive backup archives
# can be exfiltrated due to a wildcard trust relationship.

resource "aws_s3_bucket" "disaster_recovery_backups" {
  bucket = "corp-enterprise-dr-backups"

  tags = {
    Classification = "Restricted"
    Purpose        = "DatabaseBackups"
  }
}

# Contextual violation: Wildcard principal in trust policy allows arbitrary external AWS accounts (POL-IAM-005)
resource "aws_iam_role" "dr_replication_role" {
  name = "enterprise-dr-cross-account-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*" # Wildcard principal: any AWS account can attempt assume-role
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "dr_backup_access" {
  name = "dr-backup-readwrite-policy"
  role = aws_iam_role.dr_replication_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.disaster_recovery_backups.arn,
          "${aws_s3_bucket.disaster_recovery_backups.arn}/*"
        ]
      }
    ]
  })
}

