# COMPLEX MISCONFIG — no single resource looks wrong in isolation.
# The flaw only emerges from the relationship between three resources:
# an EC2 instance -> an over-permissive IAM role -> a private S3 bucket.
# Static scanners typically miss this; it needs contextual reasoning.

resource "aws_iam_role" "app_role" {
  name = "app-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "app_role_policy" {
  name = "app-role-policy"
  role = aws_iam_role.app_role.id

  # Looks reasonable on its own: scoped to one bucket ARN.
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = ["arn:aws:s3:::internal-secrets-bucket", "arn:aws:s3:::internal-secrets-bucket/*"]
    }]
  })
}

resource "aws_iam_instance_profile" "app_profile" {
  name = "app-instance-profile"
  role = aws_iam_role.app_role.name
}

resource "aws_instance" "web_app" {
  ami                  = "ami-0123456789abcdef0"
  instance_type        = "t3.micro"
  iam_instance_profile = aws_iam_instance_profile.app_profile.name
  vpc_security_group_ids = [aws_security_group.app_sg.id]
}

resource "aws_security_group" "app_sg" {
  name = "app-sg"

  # Looks fine on its own: only web ports, no SSH.
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # But this app instance is internet-facing (port 80 open to 0.0.0.0/0)
  # AND holds credentials to read/write a bucket named "internal-secrets-bucket".
  # A compromised web app on this instance inherits full read/write access
  # to secrets storage. Neither the IAM policy nor the security group is
  # individually a violation — the combination is the vulnerability.
}

resource "aws_s3_bucket" "secrets" {
  bucket = "internal-secrets-bucket"
}

resource "aws_s3_bucket_public_access_block" "secrets_block" {
  bucket                  = aws_s3_bucket.secrets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
