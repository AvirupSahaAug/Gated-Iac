# Scenario 5: Public Web App with Legacy IMDSv1 and Privileged Cloud Role
# Demonstrates an SSRF-exploitable architecture where a public instance
# without IMDSv2 token protection can leak temporary IAM credentials to steal data.

resource "aws_security_group" "web_tier_sg" {
  name        = "public-web-frontend-sg"
  description = "Allows incoming HTTP traffic from users"

  ingress {
    description = "Public HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "frontend_server_role" {
  name = "frontend-ec2-application-role"

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

resource "aws_iam_instance_profile" "frontend_profile" {
  name = "frontend-web-instance-profile"
  role = aws_iam_role.frontend_server_role.name
}

resource "aws_iam_role_policy" "param_store_access" {
  name = "parameter-store-secrets-access"
  role = aws_iam_role.frontend_server_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "secretsmanager:GetSecretValue"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_instance" "frontend_server" {
  ami                  = "ami-0c55b159cbfafe1f0"
  instance_type        = "t3.micro"
  iam_instance_profile = aws_iam_instance_profile.frontend_profile.name
  vpc_security_group_ids = [aws_security_group.web_tier_sg.id]

  # Syntactic & Contextual vulnerability: IMDSv2 is optional (IMDSv1 enabled) (POL-EC2-002 & POL-EC2-003)
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "optional" # Vulnerable to SSRF credential extraction
  }

  tags = {
    Name        = "PublicWebFrontend"
    Environment = "production"
  }
}

