# infra/persistent

spin-up / teardown 사이클에 영향받지 않는 리소스를 관리한다. 한 번 apply 한 뒤 거의 변경할 일이 없다.

## 산출물

- ACM 인증서 (`api.ku-helper.seungwoo1209.site`, DNS validation, cross-account Route53)
- EC2 IAM Role + Instance Profile (`ku-helper-ec2-role` — `prevent_destroy`)
- AMI data source — Packer 발행 `ku-helper-app-*` 의 최신 ID

## 사전 조건

1. `infra/bootstrap` apply 완료 (S3 + DynamoDB lock 존재).
2. Packer 빌드로 `ku-helper-app-*` AMI 1개 이상 발행 (`infra/packer` 참고).
3. 호스팅 존 계정에 IAM Role `Route53-kuhelper-CrossAccount-Role` 사전 구성 완료. trust 가 본 배포 계정의 root 또는 OIDC role 을 허용.

## 사용

```bash
cd infra/persistent

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init \
  -backend-config="bucket=ku-helper-tfstate-${ACCOUNT_ID}" \
  -backend-config="dynamodb_table=ku-helper-tflock" \
  -backend-config="region=ap-northeast-2"

terraform apply \
  -var "route53_account_id=${ROUTE53_PROVIDER_AWS_ID}"
```

ACM 발급에는 보통 수 분 ~ 30분 소요. validation 레코드가 cross-account Route53 에 전파되면 자동 완료.

## ephemeral 모듈에서 사용하는 출력

| output | 사용처 |
| --- | --- |
| `acm_certificate_arn` | ALB HTTPS listener |
| `route53_zone_id` | ALB alias DNS 레코드 (cross-account) |
| `ec2_instance_profile_name` | EC2 IAM 부착 |
| `app_ami_id` | EC2 ami_id |
| `db_iam_user`, `redis_iam_user`, `cache_name` | RDS / Valkey IAM 매핑 |

ephemeral 모듈은 `terraform_remote_state` data source 로 위 출력을 읽는다.

## 변경이 잦은 항목과 그렇지 않은 항목

- 자주 바뀜: `app_ami_id` (Packer 재빌드 시) — 별도 apply 불필요(data source 라 ephemeral apply 마다 다시 lookup).
- 거의 안 바뀜: ACM, IAM Role 권한 — 변경 시 코드 리뷰 + PR 필수.
- 절대 변경 금지(직접 수정 시 운영 중인 ephemeral 전체 깨짐): IAM Role 이름, Instance Profile 이름.
