variable "aws_region" {
  description = "ku-helper 리전. persistent/bootstrap 과 동일."
  type        = string
  default     = "ap-northeast-2"
}

variable "project" {
  description = "리소스 이름 접두사."
  type        = string
  default     = "ku-helper"
}

variable "tfstate_bucket" {
  description = "bootstrap 이 생성한 tfstate 버킷. terraform_remote_state 가 persistent 출력을 읽을 때 사용."
  type        = string
}

variable "developer_ip_cidr" {
  description = "bastion EC2 SSH 22 ingress 를 허용할 단일 CIDR. 예: 1.2.3.4/32. 운영 환경에서 ALL 허용 금지."
  type        = string
}

variable "github_owner" {
  description = "GitHub repo owner. github provider 가 secrets 발행."
  type        = string
  default     = "seungwoo1209"
}

variable "github_repository" {
  description = "GitHub repository 이름."
  type        = string
  default     = "ku-helper"
}

# ───── 컴퓨트 ─────

variable "app_instance_type" {
  type    = string
  default = "t3.micro"
}

variable "bastion_instance_type" {
  type    = string
  default = "t3.micro"
}

# ───── 데이터 ─────

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage_gb" {
  type    = number
  default = 20
}

variable "db_engine_version" {
  type    = string
  default = "16.4"
}

variable "db_name" {
  description = "초기 데이터베이스 이름."
  type        = string
  default     = "ku_helper"
}

variable "db_master_username" {
  description = "RDS master username — IAM 인증 사용자(`ku_helper_app`) 와 별개. 부트스트랩 SQL(rds_iam grant) 실행용."
  type        = string
  default     = "postgres"
}

# ───── 애플리케이션 시크릿 ─────
# 시크릿은 terraform 변수로 받지 않는다. terraform 은 ssm_parameters.tf 에서 placeholder
# 껍데기만 만들고, 실제 값은 GitHub Actions 워크플로가 aws ssm put-parameter 로 주입한다.
# 따라서 시크릿 평문이 terraform state(S3) 에 남지 않는다. 상세는 infra/roadmap.md 참고.
