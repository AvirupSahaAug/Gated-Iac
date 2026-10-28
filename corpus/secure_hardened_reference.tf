# Scenario 6: Secure Hardened Reference Architecture (Negative Control)
# Validates that GateIaC achieves 0% False Positive Rate on compliant, secure architectures.

resource "aws_security_group" "bastion_ssh_sg" {
  name        = "bastion-restricted-sg"
  description = "Allows SSH solely from the designated corporate VPN CIDR"

  ingress {
    description = "Restricted VPN SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["198.51.100.12/32"] # Strictly scoped corporate bastion CIDR
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_s3_bucket" "audit_archive" {
  bucket = "enterprise-audit-logs-compliant"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_encryption" {
  bucket = aws_s3_bucket.audit_archive.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_iam_role" "internal_worker_role" {
  name = "internal-least-privilege-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Strictly scoped least-privilege read-only policy
resource "aws_iam_role_policy" "read_only_audit_policy" {
  name = "audit-read-only-policy"
  role = aws_iam_role.internal_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.audit_archive.arn}/*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "worker_profile" {
  name = "internal-worker-profile"
  role = aws_iam_role.internal_worker_role.name
}

resource "aws_instance" "internal_worker" {
  ami                  = "ami-0c55b159cbfafe1f0"
  instance_type        = "t3.micro"
  iam_instance_profile = aws_iam_instance_profile.worker_profile.name
  vpc_security_group_ids = [aws_security_group.bastion_ssh_sg.id]

  # Hardened IMDSv2 token enforcement
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  tags = {
    Name        = "HardenedInternalWorker"
    Environment = "production"
    Compliance  = "CIS-Level-2"
  }
}

