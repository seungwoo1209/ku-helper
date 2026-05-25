# infra/bootstrap

Terraform 의 remote state 백엔드(S3 + DynamoDB lock)를 1회 부트스트랩하는 모듈. 이 모듈 자체는 **로컬 state** 를 사용한다(chicken-and-egg).

## 산출물

- S3 bucket `ku-helper-tfstate-<aws_account_id>` (versioning + SSE-S3 + public access block + `prevent_destroy`)
- DynamoDB table `ku-helper-tflock` (PAY_PER_REQUEST, hash_key=LockID)

## 사용

```bash
cd infra/bootstrap
terraform init
terraform apply
terraform output   # 다른 모듈의 backend 설정에 그대로 사용
```

이후 `infra/persistent` 와 `infra/ephemeral` 의 `backend.tf` 가 이 버킷을 사용한다. 두 모듈은 서로 다른 state key (`persistent/terraform.tfstate`, `ephemeral/terraform.tfstate`) 를 사용해 분리된다.

## 주의

- 이 모듈의 `terraform.tfstate` 파일은 로컬에만 있다. **분실 시 S3 버킷·DynamoDB 테이블을 import 로 복구**해야 한다.
- 운영 중에는 거의 변경할 일이 없다. 주기적으로 `terraform plan` 으로 drift 확인 정도.
- `aws_s3_bucket.tfstate.lifecycle.prevent_destroy = true` 라 `terraform destroy` 실패. 진짜 폐기 시 lifecycle 블록을 일시적으로 제거.
