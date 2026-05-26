variable "aws_region" {
  description = "ku-helper 가 배포되는 AWS 리전. 모든 모듈이 동일 리전을 사용한다."
  type        = string
  default     = "ap-northeast-2"
}

variable "project" {
  description = "리소스 이름 접두사. 변경 비권장."
  type        = string
  default     = "ku-helper"
}
