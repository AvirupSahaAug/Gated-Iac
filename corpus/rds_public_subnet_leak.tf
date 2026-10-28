# Scenario 3: Relational Database Exposed via Direct Internet Ingress
# Demonstrates an architectural data exposure flaw where an RDS database
# is placed in a public subnet with publicly_accessible=true and an open SG.

resource "aws_security_group" "db_sg" {
  name        = "production-database-sg"
  description = "Security group for application database"
  vpc_id      = "vpc-12345678"

  # Contextual flaw: Ingress allows connections from anywhere in the world
  ingress {
    description = "PostgreSQL public ingress"
    from_port   = 5432
    to_port     = 5432
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

resource "aws_db_instance" "prod_database" {
  allocated_storage      = 50
  engine                 = "postgres"
  engine_version         = "15.3"
  instance_class         = "db.t3.medium"
  db_name                = "production_customer_data"
  username               = "dbadmin"
  password               = "TempProductionPassword2026!"
  skip_final_snapshot    = true
  vpc_security_group_ids = [aws_security_group.db_sg.id]

  # Syntactic violation: storage encryption disabled (POL-RDS-001)
  storage_encrypted      = false

  # Contextual violation: Database instance is directly reachable over the internet (POL-RDS-002)
  publicly_accessible    = true

  tags = {
    Environment = "production"
    Confidentiality = "Critical"
  }
}

