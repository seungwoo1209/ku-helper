# Infra Roadmap

ku-helper AWS 인프라(Terraform + Packer + GitHub Actions)의 잔여 작업·정책 미결 사항·잠재 부채를 추적하는 문서. 다음 세션이 인프라에 다시 들어올 때 **여기서부터 읽어서 컨텍스트를 복구**할 것.

마지막 갱신: 2026-05-25 — 인프라 재구성 PR 진행 중(issue #34, 브랜치 `infra/aws-rebuild`). 기존 infra/*.tf + `.github/workflows/deploy-api-server.yml` 폐기. 새 구조 `infra/{bootstrap,persistent,ephemeral,packer}/` 작성 중.

## 0. 설계 원칙

- **재현성**: 모든 AWS 리소스는 Terraform/Packer 로 코드화. 콘솔 수동 변경 금지.
- **비용 캡**: 학생 프로젝트 — t3.micro·t4g.micro·serverless 최소. NAT GW, Multi-AZ RDS, 정기 EC2 24/7 미사용 시 teardown 권장.
- **자격증명 0 정적**: 모든 외부 자격은 OIDC + IAM Role assume. GitHub Actions 의 정적 AWS Access Key 사용 금지.
- **데이터 보존**: RDS 는 `skip_final_snapshot=false` + manual snapshot 이중. teardown 으로 데이터 손실 없게.
- **사전 발급 vs 사이클**: ACM·EC2 IAM Role·AMI 는 persistent 모듈. VPC·EC2·RDS·Valkey 는 ephemeral 모듈 (한 번에 올리고 한 번에 내릴 수 있어야 함).
- **태그 강제**: 모든 AWS 리소스에 `project = "ku-helper"` (cost allocation 추적용).

## 1. 진행 상황 스냅샷

진행 중(이번 PR 범위):
1. `infra/bootstrap/` — S3 tfstate + DynamoDB lock
2. `infra/persistent/` — ACM(api.ku-helper.seungwoo1209.site) + EC2 IAM Role + AMI data
3. `infra/ephemeral/` — VPC(2AZ) + ALB + EC2 × 2 + RDS PG + Valkey serverless
4. `infra/packer/` — app AMI (docker, compose, awscli, cloudwatch agent, ssm-agent)
5. `backend/Dockerfile` + `infra/packer/files/docker-compose.yml`
6. backend/bot IAM DB 인증 코드 (`app/core/aws_auth.py`)
7. `.github/workflows/{deploy-backend-bot-startup,deploy-backend,deploy-bot,spin-up,teardown}.yml`

사전 등록 완료 (이번 IaC 가 생성하지 않음 — 변수/data 참조만):
- GitHub Actions Secret `DEPLOYMENT_AWS_ACCOUNT_ID`, `ROUTE53_PROVIDER_AWS_ID`
- IAM Role `ku-helper-github-oidc-role` (배포 계정)
- IAM Role `Route53-kuhelper-CrossAccount-Role` (Route53 계정)

애플리케이션 시크릿은 GitHub Actions Secret 으로 두지 않는다. AWS SSM Parameter Store 를 단일 원본으로 삼고, 값은 사람이 1회 수동 등록한다(아래 "시크릿 관리 방식" 참고). 따라서 워크플로 동작에 필요한 GitHub Secret 은 다음 둘뿐이다(이미 사전 등록 완료).

| Secret | 용도 |
| --- | --- |
| `DEPLOYMENT_AWS_ACCOUNT_ID` | OIDC assume role ARN 조립 (배포 설정, 시크릿 아님) |
| `ROUTE53_PROVIDER_AWS_ID` | cross-account Route53 provider assume (배포 설정, 시크릿 아님) |

teardown.yml 은 secrets 인풋이 필요 없다(workflow_dispatch confirm 문자열만).

### 시크릿 관리 방식 (GitHub Secret 미사용, terraform state 평문 방지)

시크릿은 terraform 도, GitHub 도 값을 보관하지 않는다. AWS SSM Parameter Store(SecureString)만 시크릿을 보관한다.

- **terraform 은 시크릿 파라미터를 만들지도 관리하지도 않는다.** `scripts/bootstrap-secrets-to-parameter-store.sh` 가 `/ku-helper/app/*` 시크릿과 `/ku-helper/ghcr/pat` 를 생성하고 값을 채운다. terraform 이 placeholder 라도 만들면 스크립트와 생성 주체가 겹쳐 `ParameterAlreadyExists` 충돌이 나기 때문이다. 시크릿은 SSM 이 단일 원본이며, terraform state 와 GitHub 어디에도 평문이 남지 않는다.
- 시크릿이 teardown 으로 사라지지 않는 이유는 시크릿 파라미터가 어떤 terraform 모듈에도 속하지 않기 때문이다. ephemeral teardown 은 자기 모듈 리소스만 destroy 하므로 SSM 시크릿은 그대로 유지된다. 즉 1회 등록하면 teardown 과 spin-up 을 반복해도 재등록이 필요 없다.
- EC2 의 `/opt/ku-helper/refresh-env.sh`(Packer AMI 에 포함)가 SSM 에서 값을 fetch 하여 `/etc/ku-helper/app.env` 를 작성하고 GitHub Container Registry 에 로그인한다. 첫 부팅(user-data)과 일상 배포 rollout(spin-up, deploy-backend, deploy-bot)이 모두 같은 스크립트를 호출한다.

#### 시크릿 최초 등록 (인프라 첫 구성 시 1회)

`scripts/bootstrap-secrets-to-parameter-store.sh` 가 로컬 `backend/.env` 와 `bot/.env` 를 읽어 SSM 에 등록한다. JWT 시크릿은 매 실행 새로 생성하여 `.env` 에도 역으로 갱신한다.

```bash
export AWS_PROFILE=<배포 계정 SSO 프로파일>
./scripts/bootstrap-secrets-to-parameter-store.sh --profile <배포 계정 SSO 프로파일>
```

`.env` 를 쓰지 않고 직접 등록하려면 아래처럼 한다. 필수 시크릿은 반드시 등록하고, 선택 시크릿은 해당 알림 기능을 쓸 때만 등록한다(미등록 시 애플리케이션이 미설정으로 처리).

```bash
REGION=ap-northeast-2
put() { aws ssm put-parameter --region "$REGION" --name "$1" --type SecureString --overwrite --value "$2" >/dev/null; }

# 필수
put /ku-helper/app/JWT_SECRET             "$(openssl rand -base64 48)"
put /ku-helper/app/DISCORD_CLIENT_ID      "<Discord Client ID>"
put /ku-helper/app/DISCORD_CLIENT_SECRET  "<Discord Client Secret>"
put /ku-helper/app/DISCORD_BOT_TOKEN      "<Discord Bot Token>"
put /ku-helper/ghcr/pat                   "<GitHub PAT(read:packages)>"

# 선택 (해당 알림 사용 시)
put /ku-helper/app/SUBWAY_API_KEY             "<서울 공공 API 키>"
put /ku-helper/app/NAVER_SEARCH_CLIENT_ID     "<Naver Client ID>"
put /ku-helper/app/NAVER_SEARCH_CLIENT_SECRET "<Naver Client Secret>"
put /ku-helper/app/LIBRARY_SEAT_URL           "<도서관 좌석 API URL>"
put /ku-helper/app/ADMIN_DISCORD_IDS          "<관리자 Discord ID 콤마 구분>"
```

> 시크릿은 persistent apply 전에 미리 등록해도 되고 후에 해도 된다. terraform 이 이 파라미터를 건드리지 않으므로 순서 제약이 없다.

#### 시크릿 회전

`aws ssm put-parameter --overwrite` 로 값을 갱신한 뒤 `deploy-backend.yml` 또는 `deploy-bot.yml` rollout 을 실행한다. rollout 이 `refresh-env.sh` 를 다시 호출해 컨테이너가 새 값으로 재기동된다. 비시크릿 설정(ENVIRONMENT, DB_HOST, GHCR_OWNER 등)은 시크릿이 아니므로 `infra/ephemeral/ssm_parameters.tf` 에서 terraform 이 계속 값을 관리한다.

## 2. 운영 명령 (PR 머지 후 갱신)

```bash
# state backend 1회 부트스트랩
cd infra/bootstrap && terraform init && terraform apply

# AMI 빌드 (코드 변경 없으면 재빌드 불필요)
cd infra/packer && packer build app.pkr.hcl

# 영속 리소스 (ACM, IAM Role)
cd infra/persistent && terraform init && terraform apply

# spin-up / teardown (수동 검증) — 평소엔 GitHub Actions 워크플로 사용
cd infra/ephemeral && terraform apply
cd infra/ephemeral && terraform destroy   # RDS final snapshot 자동 생성
```

GitHub Actions:
- `spin-up.yml` (workflow_dispatch) — 인프라 전체 + 앱 배포 + smoke test
- `teardown.yml` (workflow_dispatch, confirm 입력 필요) — 인프라 전체 삭제 (RDS snapshot 보존)
- `deploy-backend.yml` / `deploy-bot.yml` — `push main` 시 paths-filter 로 자동 분기

## 3. 다음 작업 (이번 PR 범위 밖)

### N-1. Bastion → SSM Managed Instance 전환  (우선순위: 보통)
- **현재**: bastion EC2 가 SSH 22 포트 + 사용자 IP CIDR 제한으로 운영. SSH 키 회전·관리 부담.
- **목표**: SSM Agent 만 켜진 EC2 + `aws ssm start-session --document-name AWS-StartPortForwardingSessionToRemoteHost` 로 로컬↔RDS/Valkey 터널. SSH 포트 0개.
- **선결**: EC2 IAM Role 에 `AmazonSSMManagedInstanceCore` 첨부, bastion SG ingress 22 제거.

### N-2. CloudWatch alarm + Discord webhook  (우선순위: 보통)
- 크롤러 연속 실패, RDS CPU > 80%, ALB 5xx > 임계, Valkey DataStored > 80% 등 → SNS → Lambda → Discord webhook (관리자 DM 채널).
- 봇 측 `ADMIN_DISCORD_IDS` 와 별개 채널.

### N-3. RDS final snapshot 자동 복원  (우선순위: 낮음)
- **현재**: teardown 시 final snapshot 생성됨. 다음 spin-up 은 비어있는 신규 인스턴스.
- **목표**: `spin-up.yml` 입력 `restore_from_latest_snapshot=true` 시 `aws_db_instance.snapshot_identifier` 로 최신 final snapshot 자동 복원.

### N-4. S3 + CloudFront frontend 배포  (ADR-A3, 범위 분리)
- 별 PR. 현재 `deploy-frontend.yml` 가 어떻게 동작하는지 먼저 점검 필요.

### N-5. 멀티 환경 (staging)  (우선순위: 낮음)
- 현재 prod 단일. Terraform workspace 또는 `infra/envs/{prod,staging}/*.tfvars` 분리.

## 4. 잠재 부채 / 한계

### D-1. NAT gateway 없음 — 모든 EC2 가 public subnet 배치
- **트레이드오프**: NAT GW 월 ~$35 절감 vs private subnet EC2 사용 불가.
- **현재 안전장치**: EC2 SG ingress 는 8000(ALB SG)/22(Bastion SG)만 허용. 인터넷에서 직접 SSH/HTTP 불가능.
- **위험**: EC2 가 public IP 노출되어 있어 정찰 트래픽은 받음. SG 가 1차 방어.

### D-2. GitHub runner 가 private subnet 직통 접근 불가
- **현재**: `alembic upgrade head` 를 bastion 경유 SSH 터널로 실행. 워크플로 한 step 증가.
- **대안**: self-hosted runner (EC2 안) — 운영 부담 증가로 미채택.

### D-3. Valkey serverless 비용 변동
- ECPU + storage 가산 과금. 트래픽 폭증 시 예상 외 비용. **CloudWatch alarm 등록(N-2) 까지 수동 모니터링**.

### D-4. RDS db.t4g.micro — burst credit 의존
- 평시 트래픽이 baseline 넘으면 credit 소진 → throttle. 알림 폭증 시각대(매시 정각 등)에 모니터링 필요.

### D-5. ACM cross-account DNS 자동화는 1회성에 가까움
- Route53 호스팅 존이 별도 계정이라 `assume_role` 로 검증 레코드 생성. 호스팅 존 이전 시 `Route53-kuhelper-CrossAccount-Role` trust 갱신 필요.

## 5. 변경 이력

- 2026-05-25 — 문서 신설. infra 재구성 PR(issue #34) 시작.
