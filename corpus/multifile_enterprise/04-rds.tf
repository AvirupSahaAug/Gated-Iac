resource "aws_kms_key" "rds" {
  description             = "KMS for RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags = merge(local.common_tags, { Purpose = "rds-encryption" })
}
resource "aws_kms_alias" "rds" {
  name          = "alias/${var.project}-rds-key"
  target_key_id = aws_kms_key.rds.id
}
resource "aws_db_instance" "primary" {
  identifier              = "${var.project}-primary"
  engine                  = "postgres"
  engine_version          = var.db_engine_version
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  max_allocated_storage   = 500
  storage_encrypted       = true
  kms_key_id              = aws_kms_key.rds.arn
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  multi_az                = true
  publicly_accessible     = false
  backup_retention_period = var.backup_retention_days
  deletion_protection     = var.enable_deletion_protection
  db_name                 = "enterprise"
  username                = "admin"
  password                = "MANAGED_BY_SECRETS_MANAGER"
  tags = merge(local.common_tags, { Name = "primary-db" })
}
resource "aws_db_instance" "read_replica" {
  identifier             = "${var.project}-read-replica"
  replicate_source_db    = aws_db_instance.primary.identifier
  instance_class         = "db.r6g.large"
  storage_encrypted      = true
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.rds.id]
  tags = merge(local.common_tags, { Name = "read-replica" })
}
