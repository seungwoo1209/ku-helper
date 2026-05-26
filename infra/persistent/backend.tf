# bucket, dynamodb_table 는 terraform init 시 -backend-config 으로 주입한다.
# 워크플로에서는 bootstrap output 을 그대로 전달하며, 로컬에서는 README.md 참고.
terraform {
  backend "s3" {
    key     = "persistent/terraform.tfstate"
    encrypt = true
  }
}
