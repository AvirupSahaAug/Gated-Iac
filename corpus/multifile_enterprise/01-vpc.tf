resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = merge(local.common_tags, { Name = "${var.project}-vpc" })
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[0]
  availability_zone       = local.az_a
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, { Name = "public-a", Tier = "public" })
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[1]
  availability_zone       = local.az_b
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, { Name = "public-b", Tier = "public" })
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[0]
  availability_zone = local.az_a
  tags = merge(local.common_tags, { Name = "private-a", Tier = "private" })
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[1]
  availability_zone = local.az_b
  tags = merge(local.common_tags, { Name = "private-b", Tier = "private" })
}

resource "aws_subnet" "database_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[0]
  availability_zone = local.az_a
  tags = merge(local.common_tags, { Name = "database-a", Tier = "database" })
}

resource "aws_subnet" "database_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.database_subnet_cidrs[1]
  availability_zone = local.az_b
  tags = merge(local.common_tags, { Name = "database-b", Tier = "database" })
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.common_tags, { Name = "${var.project}-igw" })
}

resource "aws_eip" "nat_a" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "nat-eip-a" })
}

resource "aws_eip" "nat_b" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "nat-eip-b" })
}

resource "aws_nat_gateway" "a" {
  allocation_id = aws_eip.nat_a.id
  subnet_id     = aws_subnet.public_a.id
  tags          = merge(local.common_tags, { Name = "nat-gw-a" })
}

resource "aws_nat_gateway" "b" {
  allocation_id = aws_eip.nat_b.id
  subnet_id     = aws_subnet.public_b.id
  tags          = merge(local.common_tags, { Name = "nat-gw-b" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; gateway_id = aws_internet_gateway.main.id }
  tags = merge(local.common_tags, { Name = "public-rt" })
}

resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; nat_gateway_id = aws_nat_gateway.a.id }
  tags = merge(local.common_tags, { Name = "private-rt-a" })
}

resource "aws_route_table" "private_b" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0"; nat_gateway_id = aws_nat_gateway.b.id }
  tags = merge(local.common_tags, { Name = "private-rt-b" })
}

resource "aws_route_table_association" "pub_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "pub_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}
resource "aws_route_table_association" "priv_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private_a.id
}
resource "aws_route_table_association" "priv_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private_b.id
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnet-group"
  subnet_ids = [aws_subnet.database_a.id, aws_subnet.database_b.id]
  tags       = merge(local.common_tags, { Name = "db-subnet-group" })
}

resource "aws_flow_log" "vpc" {
  vpc_id               = aws_vpc.main.id
  traffic_type         = "ALL"
  log_destination      = aws_s3_bucket.flow_logs.arn
  log_destination_type = "s3"
  tags                 = merge(local.common_tags, { Name = "vpc-flow-log" })
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.region}.s3"
  route_table_ids = [aws_route_table.private_a.id, aws_route_table.private_b.id]
  tags = merge(local.common_tags, { Name = "s3-endpoint" })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${var.region}.dynamodb"
  route_table_ids = [aws_route_table.private_a.id, aws_route_table.private_b.id]
  tags = merge(local.common_tags, { Name = "dynamodb-endpoint" })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ecr-api-endpoint" })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ecr-dkr-endpoint" })
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "logs-endpoint" })
}

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
  tags = merge(local.common_tags, { Name = "ssm-endpoint" })
}
