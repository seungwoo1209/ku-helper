data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition
}

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# 최소 권한 인라인 정책:
# - RDS IAM 인증 (rds-db:connect) — DB 리소스 ID 는 ephemeral 에서 생성되므로 와일드카드.
# - ElastiCache IAM 인증 (elasticache:Connect) — 특정 cache + user ARN.
# - SSM Parameter / Secrets Manager 읽기 — /ku-helper/* 네임스페이스 한정.
# - CloudWatch 로그/메트릭 — /ku-helper/* 한정.
data "aws_iam_policy_document" "ec2_inline" {
  statement {
    sid     = "RdsIamAuth"
    actions = ["rds-db:connect"]
    resources = [
      "arn:${local.partition}:rds-db:${var.aws_region}:${local.account_id}:dbuser:*/${var.db_iam_user}",
    ]
  }

  statement {
    sid     = "ElastiCacheIamAuth"
    actions = ["elasticache:Connect"]
    resources = [
      "arn:${local.partition}:elasticache:${var.aws_region}:${local.account_id}:serverlesscache:${var.cache_name}",
      "arn:${local.partition}:elasticache:${var.aws_region}:${local.account_id}:user:${var.redis_iam_user}",
    ]
  }

  statement {
    sid = "ReadAppConfig"
    actions = [
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
    ]
    resources = [
      "arn:${local.partition}:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project}/*",
    ]
  }

  statement {
    sid       = "ReadAppSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = ["arn:${local.partition}:secretsmanager:${var.aws_region}:${local.account_id}:secret:${var.project}/*"]
  }

  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
      "logs:DescribeLogGroups",
    ]
    resources = [
      "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:log-group:/${var.project}/*",
      "arn:${local.partition}:logs:${var.aws_region}:${local.account_id}:log-group:/${var.project}/*:*",
    ]
  }

  statement {
    sid = "CloudWatchMetrics"
    actions = [
      "cloudwatch:PutMetricData",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json

  # teardown 사이클 사이에도 유지 — ephemeral 모듈이 instance_profile_name 으로 참조.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy" "ec2_inline" {
  name   = "${var.project}-ec2-inline"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_inline.json
}

# SSM Session Manager — bastion 을 SSM Managed Instance 로 전환할 때 별도 변경 없도록 사전 attach.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:${local.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project}-ec2-instance-profile"
  role = aws_iam_role.ec2.name

  lifecycle {
    prevent_destroy = true
  }
}
