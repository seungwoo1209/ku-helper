# infra/ephemeral

spin-up / teardown 사이클로 함께 생성/삭제되는 모든 리소스. 한 번에 올리고 한 번에 내릴 수 있게 설계.

## 산출물

- VPC `10.0.0.0/16`, public(2a/2c) + private(2a/2c), IGW, NAT 없음
- ALB (internet-facing, 2 AZ), TG `/health`, listener 80→443, listener 443 + persistent ACM
- EC2 app (t3.micro, public, persistent IAM Role, user-data 가 SSM 파라미터 fetch → compose up)
- EC2 bastion (t3.micro, public, SSH 22 from `developer_ip_cidr` 전용)
- RDS PG 16 db.t4g.micro (private, IAM auth, 별도 파라미터 그룹, final snapshot)
- Valkey serverless 최소(1 GB / 1000 ECPU) + IAM user group
- TLS keypair + GitHub Actions Secret `EC2_SSH_PRIVATE_KEY`
- SSM Parameter `/ku-helper/app/*` + `/ku-helper/ghcr/pat`
- Secrets Manager `ku-helper/rds/master` (부트스트랩 전용)

## 사전 조건

1. `infra/bootstrap` apply 완료
2. `infra/persistent` apply 완료 (ACM Issued, AMI lookup 가능)
3. GitHub Actions Secrets 등록 — 워크플로에서 `terraform apply -var ...` 로 주입.

## 사용 (워크플로 외 수동)

```bash
cd infra/ephemeral

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init \
  -backend-config="bucket=ku-helper-tfstate-${ACCOUNT_ID}" \
  -backend-config="dynamodb_table=ku-helper-tflock" \
  -backend-config="region=ap-northeast-2"

terraform apply \
  -var "tfstate_bucket=ku-helper-tfstate-${ACCOUNT_ID}" \
  -var "developer_ip_cidr=$(curl -s ifconfig.me)/32"
# 시크릿은 더 이상 terraform 변수로 받지 않는다.
# scripts/bootstrap-secrets-to-parameter-store.sh 로 SSM 에 직접 등록한다(infra/roadmap.md 참고).

# teardown
terraform destroy ...   # RDS final snapshot 자동 생성
```

## 첫 spin-up 후 1회: RDS IAM user grant

apply 직후에는 PostgreSQL 내부에 `ku_helper_app` role 이 없어 IAM 인증으로 접속 불가. 다음을 1회 실행:

```bash
# bastion 경유 SSH 터널
ssh -i ~/.ssh/ku-helper.pem -L 15432:$(terraform output -raw rds_endpoint):5432 ec2-user@$(terraform output -raw bastion_public_ip)

# 다른 셸에서 — master 패스워드는 Secrets Manager 에서
MASTER_PW=$(aws secretsmanager get-secret-value --secret-id $(terraform output -raw rds_master_secret_arn) --query SecretString --output text | jq -r .password)
PGPASSWORD="$MASTER_PW" psql -h localhost -p 15432 -U postgres -d ku_helper <<'SQL'
CREATE USER ku_helper_app WITH LOGIN;
GRANT rds_iam TO ku_helper_app;
GRANT ALL PRIVILEGES ON DATABASE ku_helper TO ku_helper_app;
GRANT ALL ON SCHEMA public TO ku_helper_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ku_helper_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ku_helper_app;
SQL
```

`spin-up.yml` 워크플로가 이 step 을 자동으로 실행한다 (`IF NOT EXISTS` 가드 포함).

## 주의

- `aws_instance.app` 의 `user_data_replace_on_change = true` 라 SSM 파라미터/도커 이미지 태그가 바뀌면 EC2 가 교체된다. 의도된 동작이지만 1~2분 다운타임 발생.
- 일상 배포(`deploy-backend.yml`)는 user_data 를 변경하지 않고 SSH 로 `docker compose pull && up -d` 만 한다.
- `lifecycle.ignore_changes` 에 `final_snapshot_identifier`, `password` 포함 — `timestamp()` 와 master 패스워드 변경이 매 plan 마다 noise 가 되지 않게.
