resource "random_password" "db_master" {
  length      = 32
  special     = true
  min_special = 4
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# 부트스트랩용 master password. 첫 spin-up 후 psql 로 IAM user grant 실행에만 사용.
# Secrets Manager 에 저장하여 워크플로 / bastion 에서 fetch.
resource "aws_secretsmanager_secret" "db_master" {
  name                    = "${var.project}/rds/master"
  description             = "RDS master password - bootstrap SQL 실행 전용. 일상 접속은 IAM auth 사용."
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db_master" {
  secret_id = aws_secretsmanager_secret.db_master.id
  secret_string = jsonencode({
    username = var.db_master_username
    password = random_password.db_master.result
  })
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnets"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${var.project}-db-subnets" }
}

resource "aws_db_parameter_group" "main" {
  name        = "${var.project}-pg16"
  family      = "postgres16"
  description = "ku-helper PG 16 parameters"

  parameter {
    name  = "timezone"
    value = "Asia/Seoul"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project}-pg"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_allocated_storage_gb * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_master_username
  password = random_password.db_master.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false
  multi_az               = false
  port                   = 5432

  iam_database_authentication_enabled = true

  backup_retention_period   = 7
  backup_window             = "17:00-18:00"  # UTC — KST 02:00-03:00
  maintenance_window        = "Mon:18:00-Mon:19:00"
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.project}-final-${formatdate("YYYYMMDD-hhmm", timestamp())}"
  deletion_protection       = false # spin-up/teardown 사이클 위해 false. snapshot 으로 보존.

  enabled_cloudwatch_logs_exports = ["postgresql"]

  apply_immediately = true

  tags = { Name = "${var.project}-pg" }

  lifecycle {
    ignore_changes = [
      # timestamp() 가 매 plan 마다 바뀌어 drift 유발 방지.
      final_snapshot_identifier,
      password,
    ]
  }
}
