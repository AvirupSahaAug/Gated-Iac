# Scenario 2: Serverless Function with Unauthenticated Ingress & Wildcard DynamoDB Access
# Demonstrates a multi-resource serverless data exposure vector.

resource "aws_dynamodb_table" "customer_pii" {
  name         = "customer-pii-records"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "CustomerId"

  attribute {
    name = "CustomerId"
    type = "S"
  }

  # Syntactic violation: storage encryption disabled (POL-DDB-001)
  server_side_encryption {
    enabled = false
  }

  tags = {
    Environment = "production"
    DataClass   = "Confidential"
  }
}

resource "aws_iam_role" "lambda_exec_role" {
  name = "customer_portal_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Contextual violation component: Lambda possesses full write/admin on customer data
resource "aws_iam_role_policy" "lambda_dynamo_full" {
  name = "lambda-dynamodb-full-policy"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = [
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.customer_pii.arn
      }
    ]
  })
}

resource "aws_lambda_function" "public_portal_backend" {
  function_name = "customer-public-portal"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
  filename      = "lambda.zip"
}

# Contextual violation trigger: Unauthenticated public internet invocation
resource "aws_lambda_function_url" "public_endpoint" {
  function_name      = aws_lambda_function.public_portal_backend.function_name
  authorization_type = "NONE" # Public unauthenticated access

  cors {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET"]
  }
}

