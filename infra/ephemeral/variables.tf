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

# ───── 애플리케이션 시크릿 (SSM Parameter Store 로 동기화) ─────
# 워크플로가 GitHub Secret 으로부터 `terraform apply -var ...` 로 주입한다.

variable "discord_client_id" {
  type      = string
  sensitive = true
}

variable "discord_client_secret" {
  type      = string
  sensitive = true
}

variable "discord_bot_token" {
  type      = string
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "subway_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "naver_search_client_id" {
  type      = string
  sensitive = true
  default   = ""
}

variable "naver_search_client_secret" {
  type      = string
  sensitive = true
  default   = ""
}

variable "library_seat_url" {
  type    = string
  default = ""
}

variable "admin_discord_ids" {
  description = "comma-separated discord user IDs. 봇 관리자 알림 수신자."
  type        = string
  default     = ""
}

variable "ghcr_pat" {
  description = "GHCR read:packages PAT. EC2 가 docker login ghcr.io 시 사용."
  type        = string
  sensitive   = true
}
