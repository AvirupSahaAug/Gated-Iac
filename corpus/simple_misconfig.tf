# SIMPLE MISCONFIG — should be caught by static scanners (Checkov/tfsec) alone.

resource "aws_s3_bucket" "logs" {
  bucket = "company-app-logs-bucket"
}

resource "aws_s3_bucket_acl" "logs_acl" {
  bucket = aws_s3_bucket.logs.id
  acl    = "public-read"   # VIOLATION: direct pattern match, no context needed
}

resource "aws_security_group" "web_sg" {
  name = "web-sg"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]   # VIOLATION: SSH open to the world, single-resource
  }
}
