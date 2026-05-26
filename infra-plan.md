# ku-helper AWS 인프라 재구성 (Terraform + Packer + GitHub Actions)

## Context

ku-helper 의 기존 인프라(`infra/*.tf`, `.github/workflows/deploy-api-server.yml`)는 단일 t3.micro EC2 위에 SSH rsync 로 코드를 푸시하는 구조이며, 정적 IAM Access Key, 로컬 Terraform state, IAM Role 미부착, SSH 0.0.0.0/0 등 학생 프로젝트 단계 구성이다. 본 작업은 이를 전부 폐기하고, "한 번에 올리고 한 번에 내릴 수 있는" 비용 절감형 IaC 로 재구성한다. 핵심 목표:

- **재현성**: Terraform + Packer 로 spin-up/teardown 을 워크플로 한 번에.
- **비용 절감**: t3.micro x 2 (app + bastion), Valkey serverless 최소, RDS db.t4g.micro, NAT gateway 없음.
- **자격증명 깨끗하게**: OIDC + IAM Role (정적 키 0개), RDS·Valkey 는 IAM DB 인증.
- **데이터 보존**: teardown 시 RDS 최종 스냅샷 생성 (skip_final_snapshot=false), 다음 spin-up 시 복원 가능.
- **사전 발급 리소스 분리**: ACM(api.ku-helper.seungwoo1209.site, cross-account DNS validation), Packer AMI, EC2 IAM Role 은 spin-up/teardown 사이클과 무관하게 유지.

ALB 가 Nginx 를 대체하며, 기존 `2주차_진행보고서_v2.md` 의 "EC2 내부 Nginx" 와는 차이가 있다 — 사용자 명시적으로 확정.

## 디렉터리 구조

```
infra/
├── roadmap.md                     # 인프라 진행 상황·부채·추후 작업
├── README.md                      # 운영 가이드(spin-up/teardown/SSH 터널)
├── bootstrap/                     # state 백엔드용 S3+DynamoDB (별도 init)
│   ├── main.tf                    # tfstate bucket + lock table
│   └── outputs.tf
├── persistent/                    # spin-up/teardown 으로 변하지 않음
│   ├── providers.tf               # default + route53 cross-account 2개
│   ├── backend.tf                 # S3 backend
│   ├── acm.tf                     # ACM cert + cross-account Route53 record
│   ├── iam_ec2.tf                 # EC2 instance profile (RDS/Valkey IAM auth)
│   ├── ami.tf                     # data "aws_ami" (Packer 산출물 조회)
│   ├── variables.tf
│   └── outputs.tf
├── ephemeral/                     # spin-up/teardown 사이클 리소스
│   ├── providers.tf
│   ├── backend.tf                 # S3 backend (별도 key)
│   ├── data.tf                    # persistent state remote_state_data
│   ├── vpc.tf                     # VPC, public/private subnet x 2 AZ, IGW
│   ├── sg.tf                      # ALB SG, App SG, Bastion SG, RDS SG, Valkey SG
│   ├── alb.tf                     # ALB, listener 80→443, 443+ACM, TG, /health
│   ├── ec2_app.tf                 # app EC2 (Packer AMI, user-data: compose up)
│   ├── ec2_bastion.tf             # bastion EC2 (SSH 22, 사용자 IP 제한)
│   ├── rds.tf                     # PG t4g.micro, IAM auth, snapshot 정책
│   ├── valkey.tf                  # Serverless cache + IAM user group
│   ├── keypair.tf                 # TLS RSA, GitHub secret 발행
│   ├── variables.tf
│   └── outputs.tf
├── packer/
│   ├── app.pkr.hcl                # docker, docker compose, ssm-agent, awscli v2
│   ├── files/
│   │   └── docker-compose.yml     # app EC2 가 부팅 시 사용할 compose
│   └── README.md
└── .gitignore                     # *.tfstate, *.tfplan, .terraform/, *.pem
```

기존 `infra/` 하위 모든 파일 (`vpc.tf`, `ec2.tf`, `github.tf`, `keypair.tf`, `outputs.tf`, `providers.tf`, `variables.tf`, `ssh.sh`, `.terraform/`, `terraform.tfstate*`) 삭제. `.github/workflows/deploy-api-server.yml` 삭제.

## 주요 리소스 정의 (요약)

### bootstrap (한 번만 apply, 별도 state 로컬)
- `aws_s3_bucket "tfstate"` + 버전관리·암호화·public block
- `aws_dynamodb_table "tflock"` (PAY_PER_REQUEST, hash_key=LockID)
- 모든 리소스에 `tags = { project = "ku-helper" }`

### persistent
- **ACM**: `aws_acm_certificate "api"` (DNS validation), `aws_route53_record` 은 **route53 alias provider(=Route53 계정)** 로 cross-account 생성. `ROUTE53_PROVIDER_AWS_ID` 시크릿 기반, role `arn:aws:iam::<ROUTE53_PROVIDER_AWS_ID>:role/Route53-kuhelper-CrossAccount-Role` 을 `assume_role` block 에서 사용. 검증 완료 후 `aws_acm_certificate_validation`.
- **IAM Role for EC2**:
  - `iam_ec2_role` + `iam_instance_profile`
  - 인라인 정책: `rds-db:connect` (특정 DB 사용자 ARN), `elasticache:Connect` (cache & user ARN), `ssm:GetParameter*`/`secretsmanager:GetSecretValue` (Discord 토큰 등 추후 시크릿), `ecr/ghcr` 는 GHCR 이므로 PAT 사용 (instance profile 비대상), `logs:*` (CloudWatch agent 용 최소 권한). 최소 권한.
  - **teardown 시 삭제 안 함** — `lifecycle { prevent_destroy = true }` + 의도적으로 persistent 모듈에 위치.
- **data "aws_ami"**: `name = "ku-helper-app-*"`, owner=self, `most_recent=true`.

### ephemeral
- **VPC**: 10.0.0.0/16, public(10.0.1.0/24 — 2a, 10.0.2.0/24 — 2c), private(10.0.11.0/24 — 2a, 10.0.12.0/24 — 2c). IGW 만, **NAT gateway 없음** (비용 절감 — private subnet 의 RDS/Valkey 는 outbound 인터넷 불필요, EC2 는 public subnet 배치로 인터넷 직통).
- **SG**:
  - ALB SG: ingress 80/443 0.0.0.0/0
  - App SG: ingress 8000 from ALB SG, 22 from Bastion SG
  - Bastion SG: ingress 22 from `var.developer_ip_cidr` (변수, 기본값 강제 입력)
  - RDS SG: ingress 5432 from App SG + Bastion SG
  - Valkey SG: ingress 6379 from App SG + Bastion SG
- **ALB**: internet-facing, 2 AZ. listener 80 → redirect 443, listener 443 + ACM cert → TG(8000/HTTP, healthcheck `GET /health` — backend `app/main.py` 에 이미 존재).
- **EC2 app**: t3.micro, public subnet 2a, Packer AMI, instance_profile=persistent IAM Role, user-data: GHCR 로그인(`GHCR_PAT` SSM Parameter 에서 fetch) → `docker compose pull && up -d` (compose 파일은 AMI 내 `/opt/ku-helper/docker-compose.yml`).
- **EC2 bastion**: t3.micro, public subnet 2a, 동일 AMI(과영양이지만 단순), 동일 instance profile (Valkey/RDS IAM 토큰 발급용).
- **RDS**: `aws_db_instance` `db.t4g.micro`, engine=postgres 16, `iam_database_authentication_enabled = true`, `skip_final_snapshot = false`, `final_snapshot_identifier = "ku-helper-final-${formatdate("YYYYMMDD-hhmm", timestamp())}"`, storage 20GB gp3 (최소), `multi_az = false`, **별도 파라미터 그룹** (`aws_db_parameter_group`) 으로 `timezone=Asia/Seoul`, `log_min_duration_statement=1000`, `random_page_cost=1.1`, `log_connections=on`(=all), `log_disconnections=on`(=1).
- **Valkey**: `aws_elasticache_serverless_cache` engine=valkey, **최소 ECPU/storage limit** (1 ECPU, 1 GB) — 비용 캡. `user_group_id` 로 IAM auth user group 부착. `aws_elasticache_user` (auth_mode=iam, access_string=`on ~* +@all`) + `aws_elasticache_user_group`.
- **keypair**: TLS RSA 4096 → `aws_key_pair` + `github_actions_secret "EC2_SSH_PRIVATE_KEY"`.

### CloudWatch
- 별도 리소스 정의 최소화. EC2 user-data 가 CloudWatch agent 설치(이미 AMI 에 포함), `/opt/ku-helper/logs/*.log` → log group `/ku-helper/app/{backend,bot}` 로 전송. 보고서가 명시한 "크롤러 로그" 최소 요구는 bot 컨테이너 stdout → docker journald → CloudWatch agent 경로로 충족.

## 코드 변경 (backend/bot)

IAM DB 인증 적용으로 다음 파일 수정:

- `backend/app/core/database.py` — `create_async_engine` 직전에 RDS IAM 토큰 발급 (boto3 `rds.generate_db_auth_token`), `connect_args={"ssl": "require", "password": <token>}` 식으로 주입. `event.listens_for(engine.sync_engine, "do_connect")` 핸들러로 매 커넥션 시점 재발급 (15분 만료).
- `backend/app/core/redis.py` — `Redis(host, port, username=<iam_user>, password=<elasticache_auth_token>, ssl=True)` 로 재구성. ElastiCache IAM 토큰은 SigV4 로 직접 서명(`AWSRequestsAuth` 또는 boto3 signer) — 표준 SDK 미지원이라 ~30줄 헬퍼 `app/core/aws_auth.py` 신규 작성. 15분 TTL 캐시.
- `bot/app/core/database.py`, `bot/app/core/redis.py` — 동일 패턴 적용 (헬퍼는 `bot/app/core/aws_auth.py` 로 복제 — 두 컨테이너 동일 코드 허용).
- `backend/pyproject.toml`, `bot/pyproject.toml` — `boto3` 의존성 추가.
- `backend/app/core/config.py`, `bot/app/core/config.py` — `database_url` / `redis_url` 외에 별도 host/port/user/db 필드(`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_IAM_USER`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_IAM_USER`, `AWS_REGION`) 추가. 로컬 dev 는 기존 URL 그대로 동작하도록 `USE_IAM_AUTH` 플래그(기본 False) 분기.

테스트: 기존 docker-compose.dev/test 는 그대로 동작해야 하므로 `USE_IAM_AUTH=false` 가 기본.

## 새 Dockerfile / Compose

- **`backend/Dockerfile`** 신규: multi-stage(uv builder → slim runtime), non-root user `app`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
- **`infra/packer/files/docker-compose.yml`**: backend + bot 2 서비스만. PG/Redis 컨테이너 없음(RDS/Valkey 사용). 환경변수는 EC2 user-data 가 SSM Parameter Store 에서 fetch 하여 `/etc/ku-helper/app.env` 로 떨어뜨리고 compose `env_file` 로 주입. 이미지는 `ghcr.io/seungwoo1209/ku-helper-backend:main`, `ghcr.io/seungwoo1209/ku-helper-bot:main`.

## GitHub Actions

기존 `deploy-api-server.yml` 삭제. 신규 4개 워크플로:

### `.github/workflows/deploy-backend-bot-startup.yml`
- trigger: `push` to main
- 변경 감지(`dorny/paths-filter`):
  - backend: `backend/**` **except** `backend/**/*.md`, `backend/openapi.json`, `backend/.claude/**`, `backend/ROADMAP.md`, `backend/docs/**`
  - bot: `bot/**` **except** 동일 패턴
- 각 path 변경 시 `workflow_call` 로 deploy-backend.yml / deploy-bot.yml 호출.

### `.github/workflows/deploy-backend.yml`
- `workflow_call` + `workflow_dispatch`
- jobs:
  1. **build-and-push**: OIDC → `ku-helper-github-oidc-role` assume → ghcr login → buildx → `ghcr.io/.../ku-helper-backend:main` push
  2. **migrate**: bastion 에 SSH → terraform output 의 RDS endpoint 로 IAM 토큰 발급 → `alembic upgrade head` (alembic 컨테이너를 일회성으로 run, 또는 GitHub runner 에서 직접 — runner 가 private subnet 접근 불가하므로 **bastion 경유 SSH 터널** 방식 채택)
  3. **rollout**: app EC2 에 SSH → `docker compose pull backend && docker compose up -d backend`
- 헬스체크: ALB DNS `/health` 200 대기.

### `.github/workflows/deploy-bot.yml`
- 동일 구조, 마이그레이션 단계 없음. bot 컨테이너만 pull/up.

### `.github/workflows/spin-up.yml`
- `workflow_dispatch`
- jobs:
  1. **packer-build** (옵션 인풋 `rebuild_ami=true` 일 때만): packer build → AMI ID 출력
  2. **terraform-apply-ephemeral**: OIDC → `cd infra/ephemeral` → `terraform init -backend-config=...` → `terraform apply -auto-approve` (persistent state 의 AMI/ACM/IAM 참조)
  3. **deploy-backend / deploy-bot** 호출 (`workflow_call`)
  4. **smoke-test**: `curl https://api.ku-helper.seungwoo1209.site/health`

### `.github/workflows/teardown.yml`
- `workflow_dispatch` (confirm 인풋 `confirm="TEARDOWN"` 강제)
- jobs:
  1. **pre-snapshot**: RDS manual snapshot trigger (`aws rds create-db-snapshot`) — 안전망(terraform 의 final_snapshot 이 이미 있지만 이중)
  2. **terraform-destroy**: `cd infra/ephemeral` → `terraform destroy -auto-approve`. RDS 는 `skip_final_snapshot=false` 로 자동 final snapshot 생성.

### OIDC / Secrets 사용 표
| Secret | 등록 주체 | 용도 |
| --- | --- | --- |
| `DEPLOYMENT_AWS_ACCOUNT_ID` | **사전 등록 완료** | OIDC assume role ARN(`arn:aws:iam::<ID>:role/ku-helper-github-oidc-role`) 조립 |
| `ROUTE53_PROVIDER_AWS_ID` | **사전 등록 완료** | persistent 모듈의 Route53 cross-account provider `assume_role` |
| `GHCR_PAT` | 사용자가 1회 등록 (Personal Access Token, read:packages) | Terraform 이 SSM Parameter `/ku-helper/ghcr/pat` 로 동기화 → EC2 user-data 가 docker login |
| `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_SECRET`, `JWT_SECRET`, `SUBWAY_API_KEY`, `NAVER_SEARCH_CLIENT_*` | 사용자가 1회 등록 | Terraform 이 SSM Parameter (`/ku-helper/app/*`) 로 동기화. EC2 user-data 가 fetch. |

## State 백엔드 (S3 + DynamoDB lock)

`infra/bootstrap/` 을 한 번만 수동 init/apply (로컬 state). 산출: `ku-helper-tfstate-${aws_account_id}` 버킷, `ku-helper-tflock` 테이블. `persistent` 와 `ephemeral` 은 각각 다른 state key (`persistent/terraform.tfstate`, `ephemeral/terraform.tfstate`) 로 분리. `ephemeral` 은 `terraform_remote_state` 로 persistent 출력 참조.

## roadmap.md 초기 내용

`infra/roadmap.md` 에 다음 섹션 초안:
- ✅ 완료: bootstrap, persistent, ephemeral, CI/CD 4종, IAM DB 인증
- 🔜 다음: Bastion → SSM Managed Instance 전환 (요청 명시), CloudWatch alarm + Discord webhook, Valkey 비용 모니터링, Multi-AZ 검토(예산 여유 시), S3+CloudFront frontend (현재 범위 밖)
- 📋 부채: NAT gateway 없어서 private EC2 불가 (현재 모든 EC2 public 배치), GitHub runner → private subnet 직통 접근 (현재 bastion 경유)

## 사전 작업 / 사용자 확정 사항 (반영 완료)

- RDS·Valkey IAM 인증 적용, backend/bot 코드 변경 포함
- TF state: S3 + DynamoDB lock
- Backend Dockerfile 이번 PR 에 포함
- Frontend(S3+CloudFront) 범위 제외

### 이미 외부에 구성 완료된 자산 (이번 IaC 가 생성/등록하지 않음)

- **GitHub Actions Secret `DEPLOYMENT_AWS_ACCOUNT_ID`** — 배포 대상 AWS 계정 ID. 이미 등록됨. 워크플로에서 `${{ secrets.DEPLOYMENT_AWS_ACCOUNT_ID }}` 로 참조만.
- **GitHub Actions Secret `ROUTE53_PROVIDER_AWS_ID`** — Route53 호스팅 존을 보유한 별도 AWS 계정 ID. 이미 등록됨. persistent 모듈의 cross-account provider `assume_role` 에서 참조만.
- **IAM Role `ku-helper-github-oidc-role`** (배포 계정) — GitHub OIDC trust 사전 설정 완료. 모든 워크플로가 이 role 을 assume. Terraform 으로 다시 만들지 않음.
- **IAM Role `Route53-kuhelper-CrossAccount-Role`** (Route53 계정) — cross-account DNS 레코드 생성 권한. persistent 모듈의 Route53 provider 가 assume.

→ `infra/persistent`, `infra/ephemeral` 어디서도 위 4개 항목의 `aws_iam_role` / `github_actions_secret` 리소스 정의를 추가하지 않는다. 변수 또는 `data` 블록으로만 참조한다.

## 계획 산출물 위치

본 계획 파일이 사용자 승인되면, 동일 내용을 레포 루트의 **`infra-plan.md`** 로 복사한다. GitHub issue 본문에서 이 파일을 링크한다.

## 작업 순서

1. **GitHub issue 생성** — `infra-plan.md` 링크 + 체크리스트 게시. 브랜치 `infra/aws-rebuild` 연결.
2. **기존 인프라 파일 삭제** (`infra/*.tf`, `ssh.sh`, `terraform.tfstate*`, `.terraform.lock.hcl`, `.terraform/`, `.github/workflows/deploy-api-server.yml`).
3. **infra/roadmap.md 작성**.
4. **bootstrap 모듈** 작성·로컬 apply.
5. **packer 템플릿** 작성·로컬 build·AMI 산출.
6. **persistent 모듈** 작성·apply (ACM 발급 시 cross-account DNS 검증 대기).
7. **ephemeral 모듈** 작성 (apply 는 spin-up.yml 으로 자동화 검증).
8. **backend/Dockerfile**, **packer/files/docker-compose.yml** 작성.
9. **backend/bot 코드 변경** (IAM DB 인증) + 단위테스트 갱신.
10. **GitHub Actions 4종** (`deploy-backend-bot-startup.yml`, `deploy-backend.yml`, `deploy-bot.yml`, `spin-up.yml`, `teardown.yml`) 작성.
11. **PR 생성**.

## 검증 (Verification)

- **bootstrap**: `cd infra/bootstrap && terraform apply` → S3 버킷·DynamoDB 테이블 콘솔 확인.
- **packer**: `packer build infra/packer/app.pkr.hcl` → AWS EC2 → AMI 콘솔에서 `ku-helper-app-*` 확인.
- **persistent**: `cd infra/persistent && terraform apply` → ACM "Issued", IAM Role 콘솔 확인.
- **spin-up 수동**: GitHub Actions 에서 `spin-up.yml` 디스패치 → ALB DNS 출력 → `curl https://api.ku-helper.seungwoo1209.site/health` 200 확인 → backend `/docs` 접근 → discord bot 의 startup 로그 CloudWatch 확인.
- **마이그레이션**: 새 alembic revision 1개 추가 후 main push → workflow 가 `alembic upgrade head` 실행, bastion 경유 RDS 에 반영 확인.
- **bastion 터널**: `ssh -i ~/.ssh/ku-helper.pem -L 15432:<rds-endpoint>:5432 ec2-user@<bastion-ip>` → 로컬 datagrip 으로 RDS 접속 확인. Valkey 도 6379 포트포워딩.
- **teardown**: `teardown.yml` 디스패치 → RDS snapshot 콘솔 확인 → 모든 ephemeral 리소스 destroyed.
- **재 spin-up**: 다음 spin-up 시 RDS 가 비어있는 신규 인스턴스로 재생성됨 (snapshot 복원은 별도 수동 작업 — roadmap 항목으로 자동화).
